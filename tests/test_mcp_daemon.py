import http.client
import io
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from codex_agent_mem import __version__
from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event
from codex_agent_mem.mcp_daemon import _make_handler, _validate_bind_host
from codex_agent_mem.mcp_stdio import CodexAgentMemMCPServer, LazyStoreProvider, MCPRuntimeState, _forward_to_daemon


@contextmanager
def run_server(handler: type):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()
        assert not thread.is_alive()


def post_json(
    base_url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    parsed = urllib.parse.urlparse(base_url.rstrip("/") + "/mcp")
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    request_headers = {"Content-Type": "application/json", "Connection": "close", **(headers or {})}
    try:
        connection.request("POST", parsed.path, body=body, headers=request_headers)
        response = connection.getresponse()
        response_body = response.read()
        if response.status >= 400:
            raise urllib.error.HTTPError(
                parsed.geturl(),
                response.status,
                response.reason,
                response.headers,
                io.BytesIO(response_body),
            )
        if response.status == 204:
            return None
        return json.loads(response_body.decode("utf-8"))
    finally:
        connection.close()


def post_json_error(
    base_url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    try:
        post_json(base_url, payload, headers=headers)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    raise AssertionError("Expected HTTPError")


def get_json(base_url: str, path: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def seed_project(db_path: Path, cwd: Path) -> None:
    raw_payload = {
        "runtime": "codex",
        "project_key": "daemon-project",
        "session_id": "thread-daemon",
        "turn_id": "turn-daemon",
        "cwd": str(cwd),
        "timestamp": "2026-04-26T00:00:00Z",
        "input_messages": [
            "Objective: validate daemon bridge.\n"
            "Pending: keep daemon requests serialized.\n"
            "Blocker: avoid database is locked."
        ],
        "assistant_message": "Decision: serialize shared daemon request handling.",
        "metadata": {},
    }
    store = CodexAgentMemStore(db_path)
    try:
        store.ingest_event(raw_payload, normalize_event(raw_payload))
    finally:
        store.close()


def test_daemon_bind_host_validation_is_loopback_only():
    assert _validate_bind_host("127.0.0.1") == "127.0.0.1"
    assert _validate_bind_host("localhost") == "localhost"
    assert _validate_bind_host("::1") == "::1"

    for host in ("0.0.0.0", "192.168.1.10", "10.0.0.2", "example.internal"):
        with pytest.raises(ValueError, match="Remote daemon bind is not supported"):
            _validate_bind_host(host)


def test_daemon_http_smoke_uses_temp_db_without_opening_store(tmp_path: Path):
    db_path = tmp_path / "codex_agent_mem.db"
    runtime = MCPRuntimeState(
        db_path=db_path,
        idle_timeout_seconds=None,
        profile="minimal",
        read_only=True,
        response_mode="compact",
    )
    provider = LazyStoreProvider(db_path, runtime)
    server = CodexAgentMemMCPServer(provider, runtime)
    handler = _make_handler(server, runtime)

    try:
        with run_server(handler) as base_url:
            health = get_json(base_url, "/health")
            assert health["profile"] == "minimal"
            assert health["read_only"] is True
            assert health["server_version"] == __version__
            assert "db_path" not in health

            initialized = post_json(
                base_url,
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
            assert initialized["result"]["serverInfo"]["name"] == "codex-agent-mem"

            tools = post_json(
                base_url,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            assert {tool["name"] for tool in tools["result"]["tools"]} == {
                "mem_context_pack",
                "mem_session_list",
                "mem_scope_resolve",
                "mem_bootstrap_context",
                "mem_open_work",
                "mem_completion_check",
                "mem_health_runtime",
            }

            runtime_health = post_json(
                base_url,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "mem_health_runtime", "arguments": {}},
                },
            )
            assert runtime_health["result"]["structuredContent"]["lazy_initialized"] is False
            assert runtime_health["result"]["structuredContent"]["requests_count"] == 3
            assert not db_path.exists()
    finally:
        provider.close()


def test_daemon_auth_token_protects_mcp_but_not_health(tmp_path: Path):
    db_path = tmp_path / "codex_agent_mem.db"
    runtime = MCPRuntimeState(
        db_path=db_path,
        idle_timeout_seconds=None,
        profile="minimal",
        read_only=True,
        response_mode="compact",
    )
    provider = LazyStoreProvider(db_path, runtime)
    server = CodexAgentMemMCPServer(provider, runtime)
    token = "local-test-token"
    handler = _make_handler(server, runtime, auth_token=token)

    try:
        with run_server(handler) as base_url:
            health = get_json(base_url, "/health")
            assert health["server_version"] == __version__
            assert "db_path" not in health
            assert token not in json.dumps(health, ensure_ascii=True)

            status, body = post_json_error(
                base_url,
                {"jsonrpc": "2.0", "id": 10, "method": "initialize", "params": {}},
            )
            assert status == 401
            assert body == {"error": "unauthorized"}
            assert token not in json.dumps(body, ensure_ascii=True)

            status, body = post_json_error(
                base_url,
                {"jsonrpc": "2.0", "id": 11, "method": "initialize", "params": {}},
                headers={"Authorization": "Bearer wrong-token"},
            )
            assert status == 401
            assert body == {"error": "unauthorized"}

            initialized = post_json(
                base_url,
                {"jsonrpc": "2.0", "id": 12, "method": "initialize", "params": {}},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert initialized["result"]["serverInfo"]["name"] == "codex-agent-mem"
    finally:
        provider.close()


def test_stdio_bridge_forwards_daemon_token(tmp_path: Path):
    db_path = tmp_path / "codex_agent_mem.db"
    runtime = MCPRuntimeState(
        db_path=db_path,
        idle_timeout_seconds=None,
        profile="minimal",
        read_only=True,
        response_mode="compact",
    )
    provider = LazyStoreProvider(db_path, runtime)
    server = CodexAgentMemMCPServer(provider, runtime)
    token = "bridge-token"
    handler = _make_handler(server, runtime, auth_token=token)
    message = {"jsonrpc": "2.0", "id": 13, "method": "initialize", "params": {}}

    try:
        with run_server(handler) as base_url:
            unauthorized = _forward_to_daemon(base_url, message)
            assert unauthorized["jsonrpc"] == "2.0"
            assert unauthorized["id"] == 13
            assert unauthorized["error"]["code"] in {-32001, -32002}
            if unauthorized["error"]["code"] == -32001:
                assert unauthorized["error"]["message"] == "daemon HTTP 401: unauthorized"
            else:
                assert unauthorized["error"]["message"].startswith("daemon transport error:")

            initialized = _forward_to_daemon(base_url, message, daemon_token=token)
            assert initialized["result"]["serverInfo"]["name"] == "codex-agent-mem"
    finally:
        provider.close()


def test_daemon_db_backed_context_pack_uses_temp_db(tmp_path: Path):
    db_path = tmp_path / "codex_agent_mem.db"
    workspace = tmp_path / "daemon-project"
    workspace.mkdir()
    seed_project(db_path, workspace)
    runtime = MCPRuntimeState(
        db_path=db_path,
        idle_timeout_seconds=None,
        profile="minimal",
        read_only=True,
        response_mode="compact",
    )
    provider = LazyStoreProvider(db_path, runtime)
    server = CodexAgentMemMCPServer(provider, runtime)
    handler = _make_handler(server, runtime)

    try:
        with run_server(handler) as base_url:
            result = post_json(
                base_url,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "mem_context_pack", "arguments": {"project_key": "daemon-project"}},
                },
            )

            assert result["result"]["isError"] is False
            assert result["result"]["structuredContent"]["pack_hash"]
            assert runtime.lazy_initialized is True
            assert provider.get().conn.execute("PRAGMA query_only;").fetchone()[0] == 1
    finally:
        provider.close()


def test_daemon_serializes_shared_mcp_server_requests(tmp_path: Path):
    class SlowServer:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def handle_request(self, message: dict[str, Any]) -> dict[str, Any]:
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.05)
            with self.lock:
                self.active -= 1
            return {"jsonrpc": "2.0", "id": message.get("id"), "result": {"ok": True}}

    runtime = MCPRuntimeState(db_path=tmp_path / "codex_agent_mem.db", idle_timeout_seconds=None)
    slow_server = SlowServer()
    handler = _make_handler(slow_server, runtime)  # type: ignore[arg-type]

    with run_server(handler) as base_url:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda request_id: post_json(
                        base_url,
                        {"jsonrpc": "2.0", "id": request_id, "method": "ping", "params": {}},
                    ),
                    range(8),
                )
            )

    assert [result["result"] for result in results] == [{"ok": True}] * 8
    assert slow_server.max_active == 1
