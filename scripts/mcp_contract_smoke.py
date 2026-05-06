from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from codex_agent_mem import __version__  # noqa: E402
from codex_agent_mem.db import CodexAgentMemStore  # noqa: E402
from codex_agent_mem.ingest import normalize_event  # noqa: E402
from codex_agent_mem.mcp_stdio import CodexAgentMemMCPServer, MCPRuntimeState  # noqa: E402


PROJECT_KEY = "mcp-contract-smoke"


class SmokeFailure(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _seed_store(store: CodexAgentMemStore, workspace: Path) -> None:
    payloads = [
        {
            "runtime": "codex",
            "project_key": PROJECT_KEY,
            "session_id": "contract-session",
            "turn_id": "contract-turn-1",
            "cwd": str(workspace),
            "timestamp": "2026-04-26T00:00:00Z",
            "input_messages": [
                "Objective: validate the MCP contract smoke.\n"
                "Pending: keep list results wrapped as object-root structuredContent.\n"
                "Session DoD: verify known_pack_hash returns not_modified."
            ],
            "assistant_message": (
                "Decision: use a temporary SQLite database only. "
                "Pending: verify the context pack hash handshake."
            ),
            "metadata": {"source": "scripts/mcp_contract_smoke.py"},
        },
        {
            "runtime": "codex",
            "project_key": PROJECT_KEY,
            "session_id": "contract-session-sibling",
            "turn_id": "contract-turn-2",
            "cwd": str(workspace),
            "timestamp": "2026-04-26T00:01:00Z",
            "input_messages": [
                "Objective: validate sibling session scope warnings.\n"
                "Pending: make project-wide retrieval visibly cautious."
            ],
            "assistant_message": "Pending: verify mem_session_list + session_id guidance is visible.",
            "metadata": {"source": "scripts/mcp_contract_smoke.py"},
        },
    ]
    for payload in payloads:
        store.ingest_event(payload, normalize_event(payload))


def _expect_result(response: dict[str, Any] | None, expected_id: int) -> dict[str, Any]:
    _require(response is not None, f"request id {expected_id} returned no response")
    _require(response.get("jsonrpc") == "2.0", f"request id {expected_id} missing jsonrpc=2.0")
    _require(response.get("id") == expected_id, f"request id {expected_id} returned mismatched id")
    if "error" in response:
        raise SmokeFailure(f"request id {expected_id} returned error: {response['error']}")
    result = response.get("result")
    _require(isinstance(result, dict), f"request id {expected_id} result is not an object")
    return result


def _expect_tool_payload(
    response: dict[str, Any] | None,
    expected_id: int,
    tool_name: str,
) -> dict[str, Any]:
    result = _expect_result(response, expected_id)
    _require(result.get("isError") is False, f"{tool_name} returned isError=true")
    content = result.get("content")
    _require(isinstance(content, list) and content, f"{tool_name} missing text content")
    _require(content[0].get("type") == "text", f"{tool_name} content[0] is not text")
    _require(isinstance(content[0].get("text"), str), f"{tool_name} text is not a string")
    structured = result.get("structuredContent")
    _require(isinstance(structured, dict), f"{tool_name} structuredContent root is not an object")
    return structured


def _expect_wrapped_list(payload: dict[str, Any], tool_name: str) -> None:
    _require(isinstance(payload.get("items"), list), f"{tool_name} did not expose items list")
    _require(isinstance(payload.get("count"), int), f"{tool_name} did not expose count integer")
    _require(
        payload["count"] == len(payload["items"]),
        f"{tool_name} count does not match items length",
    )


def _expect_temp_db(payload: dict[str, Any], temp_root: Path) -> None:
    db_path = payload.get("db_path")
    _require(isinstance(db_path, str) and db_path, "runtime health did not expose db_path")
    resolved_db = Path(db_path).resolve()
    resolved_root = temp_root.resolve()
    _require(
        resolved_db.is_relative_to(resolved_root),
        f"runtime db_path is not under the smoke temp directory: {resolved_db}",
    )


def _exercise_contract(
    send: Callable[[dict[str, Any]], dict[str, Any] | None],
    *,
    temp_root: Path,
) -> dict[str, Any]:
    next_id = 1

    def request(
        method: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any] | None]:
        nonlocal next_id
        request_id = next_id
        next_id += 1
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        return request_id, send(message)

    def tool_result(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        request_id, response = request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        result = _expect_result(response, request_id)
        _require(result.get("isError") is False, f"{name} returned isError=true")
        content = result.get("content")
        _require(isinstance(content, list) and content, f"{name} missing text content")
        _require(content[0].get("type") == "text", f"{name} content[0] is not text")
        _require(isinstance(content[0].get("text"), str), f"{name} text is not a string")
        structured = result.get("structuredContent")
        _require(isinstance(structured, dict), f"{name} structuredContent root is not an object")
        return result

    def tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return tool_result(name, arguments)["structuredContent"]

    request_id, response = request("initialize", {})
    initialized = _expect_result(response, request_id)
    _require(
        initialized.get("serverInfo", {}).get("name") == "codex-agent-mem",
        "initialize returned the wrong server name",
    )
    _require(
        initialized.get("serverInfo", {}).get("version") == __version__,
        "initialize returned the wrong server version",
    )
    _require(
        isinstance(initialized.get("capabilities", {}).get("tools"), dict),
        "tools capability missing",
    )

    request_id, response = request("tools/list", {})
    tools_result = _expect_result(response, request_id)
    tools = tools_result.get("tools")
    _require(isinstance(tools, list) and tools, "tools/list returned no tools")
    tool_names = {str(item.get("name")) for item in tools if isinstance(item, dict)}
    for expected in {
        "mem_context_pack",
        "mem_health_runtime",
        "mem_recent",
        "mem_search",
        "mem_session_list",
        "mem_note_create",
        "mem_snapshot_create",
    }:
        _require(expected in tool_names, f"tools/list missing {expected}")

    runtime_health = tool("mem_health_runtime", {})
    _require(runtime_health.get("profile") == "full", "runtime profile is not full")
    _require(runtime_health.get("read_only") is False, "runtime is unexpectedly read-only")
    _require(
        runtime_health.get("response_mode") == "compact",
        "runtime response mode is not compact",
    )
    _expect_temp_db(runtime_health, temp_root)

    search = tool("mem_search", {"query": "", "project_key": PROJECT_KEY, "limit": 5})
    _expect_wrapped_list(search, "mem_search")
    _require(search["count"] >= 1, "mem_search did not return the seeded observation")

    recent = tool("mem_recent", {"project_key": PROJECT_KEY, "limit": 5})
    _expect_wrapped_list(recent, "mem_recent")
    _require(recent["count"] >= 1, "mem_recent did not return the seeded observation")

    sessions = tool("mem_session_list", {"project_key": PROJECT_KEY, "limit": 5})
    _expect_wrapped_list(sessions, "mem_session_list")
    _require(sessions["count"] >= 1, "mem_session_list did not return the seeded session")
    query_sessions = tool("mem_session_list", {"project_key": PROJECT_KEY, "query": "sibling", "limit": 5})
    _expect_wrapped_list(query_sessions, "mem_session_list query")
    _require(query_sessions["count"] == 1, "mem_session_list query did not narrow to the sibling session")
    scoped_session_id = int(query_sessions["items"][0]["session_id"])

    note_phrase = "manual note contract phrase 20260429 searchable continuity"
    created_note = tool(
        "mem_note_create",
        {
            "project_key": PROJECT_KEY,
            "text": note_phrase,
            "session_id": scoped_session_id,
            "title": "Contract manual note",
            "tags": ["contract", "continuity"],
            "importance": 5,
        },
    )
    _require(isinstance(created_note.get("observation_id"), int), "mem_note_create did not return an observation id")
    _require(created_note.get("source_kind") == "manual_note", "mem_note_create did not mark manual source_kind")
    _require(created_note.get("session_id") == scoped_session_id, "mem_note_create did not preserve session_id")
    _require(
        created_note.get("provenance_confidence") == "high",
        "mem_note_create did not record high-confidence provenance",
    )

    note_search = tool(
        "mem_search",
        {"query": note_phrase, "project_key": PROJECT_KEY, "session_id": scoped_session_id, "limit": 5},
    )
    _expect_wrapped_list(note_search, "mem_search note")
    _require(note_search["count"] >= 1, "mem_search did not find the manual note")
    _require(
        note_search["items"][0].get("id") == created_note["observation_id"],
        "mem_search did not return the manual note observation",
    )

    note_pack = tool("mem_context_pack", {"project_key": PROJECT_KEY, "budget": "full", "session_id": scoped_session_id})
    _require(note_phrase in note_pack.get("text", ""), "mem_context_pack did not include the manual note")

    created_snapshot = tool(
        "mem_snapshot_create",
        {
            "project_key": PROJECT_KEY,
            "label": "writable-contract-smoke",
            "session_id": scoped_session_id,
        },
    )
    _require(isinstance(created_snapshot.get("id"), int), "mem_snapshot_create did not return a snapshot id")
    _require(
        created_snapshot.get("session_id") == scoped_session_id,
        "created snapshot did not preserve the requested session_id",
    )
    _require(
        created_snapshot.get("provenance_confidence") == "high",
        "created snapshot did not record high-confidence provenance",
    )
    _require(
        created_snapshot.get("provenance_warning") is None,
        "created snapshot unexpectedly emitted a provenance warning",
    )

    snapshots = tool("mem_snapshot_list", {"project_key": PROJECT_KEY})
    _expect_wrapped_list(snapshots, "mem_snapshot_list")
    _require(
        any(item.get("id") == created_snapshot["id"] for item in snapshots["items"]),
        "mem_snapshot_list did not return the writable snapshot",
    )

    pack_result = tool_result("mem_context_pack", {"project_key": PROJECT_KEY, "budget": "auto"})
    pack = pack_result["structuredContent"]
    compact_text = pack_result["content"][0]["text"]
    pack_hash = pack.get("pack_hash")
    _require(isinstance(pack.get("text"), str) and pack["text"], "context pack text is missing")
    _require(isinstance(pack_hash, str) and pack_hash, "context pack hash is missing")
    _require("session_filter=not_applied" in compact_text, "context pack compact text missing session filter")
    _require("source_sessions=" in compact_text, "context pack compact text missing source session count")
    _require(
        "scope_warning=multi_session_project_scope" in compact_text,
        "context pack compact text missing scope warning",
    )
    _require(
        "mem_session_list + session_id" in compact_text,
        "context pack compact text missing narrowing hint",
    )
    _require("persisted local context" in compact_text, "context pack compact text missing persisted-memory note")
    _require(
        "not live current-turn awareness" in compact_text,
        "context pack compact text missing live-awareness caveat",
    )
    _require("Scope warning:" in pack["text"], "context pack text missing scope warning")
    _require(
        "Objective (project-wide candidate)" not in pack["text"],
        "context pack text exposed an ambiguous project-wide objective",
    )
    _require(
        "No active objective selected" in pack["text"],
        "context pack text missing ambiguous-objective suppression notice",
    )

    scoped_pack_result = tool_result(
        "mem_context_pack",
        {"project_key": PROJECT_KEY, "budget": "auto", "session_id": scoped_session_id},
    )
    scoped_pack = scoped_pack_result["structuredContent"]
    scoped_text = scoped_pack_result["content"][0]["text"]
    _require(
        scoped_pack["stats"].get("session_filter_applied") is True,
        "scoped context pack did not apply session filter",
    )
    _require(
        scoped_pack["stats"].get("source_session_count") == 1,
        "scoped context pack did not narrow source sessions to one",
    )
    _require(
        "session_filter=applied" in scoped_text,
        "scoped context pack compact text missing applied session filter",
    )

    unchanged = tool(
        "mem_context_pack",
        {"project_key": PROJECT_KEY, "budget": "auto", "known_pack_hash": pack_hash},
    )
    _require(unchanged.get("not_modified") is True, "known_pack_hash did not return not_modified")
    _require(unchanged.get("pack_hash") == pack_hash, "not_modified returned a different pack_hash")
    return {
        "note_phrase": note_phrase,
        "note_observation_id": created_note["observation_id"],
        "scoped_session_id": scoped_session_id,
    }


def _exercise_later_process_retrieval(
    send: Callable[[dict[str, Any]], dict[str, Any] | None],
    *,
    temp_root: Path,
    note_phrase: str,
    scoped_session_id: int,
    note_observation_id: int,
) -> None:
    next_id = 1

    def request(
        method: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any] | None]:
        nonlocal next_id
        request_id = next_id
        next_id += 1
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        return request_id, send(message)

    def tool_result(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        request_id, response = request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        result = _expect_result(response, request_id)
        _require(result.get("isError") is False, f"{name} returned isError=true")
        structured = result.get("structuredContent")
        _require(isinstance(structured, dict), f"{name} structuredContent root is not an object")
        return result

    def tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return tool_result(name, arguments)["structuredContent"]

    request_id, response = request("initialize", {})
    initialized = _expect_result(response, request_id)
    _require(
        initialized.get("serverInfo", {}).get("version") == __version__,
        "later subprocess initialize returned the wrong server version",
    )

    runtime_health = tool("mem_health_runtime", {})
    _require(runtime_health.get("profile") == "full", "later subprocess profile is not full")
    _require(runtime_health.get("read_only") is False, "later subprocess is unexpectedly read-only")
    _expect_temp_db(runtime_health, temp_root)

    note_search = tool(
        "mem_search",
        {
            "query": note_phrase,
            "project_key": PROJECT_KEY,
            "session_id": scoped_session_id,
            "limit": 5,
        },
    )
    _expect_wrapped_list(note_search, "later mem_search note")
    _require(note_search["count"] >= 1, "later subprocess did not find the manual note")
    _require(
        any(item.get("id") == note_observation_id for item in note_search["items"]),
        "later subprocess did not return the manual note observation",
    )

    note_pack = tool(
        "mem_context_pack",
        {"project_key": PROJECT_KEY, "budget": "full", "session_id": scoped_session_id},
    )
    _require(
        note_phrase in note_pack.get("text", ""),
        "later subprocess context pack did not include the manual note",
    )
    pack_hash = note_pack.get("pack_hash")
    _require(isinstance(pack_hash, str) and pack_hash, "later subprocess pack hash is missing")

    unchanged = tool(
        "mem_context_pack",
        {
            "project_key": PROJECT_KEY,
            "budget": "full",
            "session_id": scoped_session_id,
            "known_pack_hash": pack_hash,
        },
    )
    _require(
        unchanged.get("not_modified") is True,
        "later subprocess known_pack_hash did not return not_modified",
    )
    _require(
        unchanged.get("pack_hash") == pack_hash,
        "later subprocess not_modified returned a different pack_hash",
    )


def _run_in_process(temp_root: Path) -> None:
    db_path = temp_root / "codex_agent_mem.db"
    workspace = temp_root / "workspace"
    workspace.mkdir()
    store = CodexAgentMemStore(db_path)
    try:
        _seed_store(store, workspace)
        runtime = MCPRuntimeState(
            db_path=db_path,
            idle_timeout_seconds=None,
            profile="full",
            read_only=False,
            response_mode="compact",
            cache_ttl_seconds=0,
        )
        server = CodexAgentMemMCPServer(store, runtime)
        _exercise_contract(server.handle_request, temp_root=temp_root)
    finally:
        store.close()


class StdioProcess:
    def __init__(self, temp_root: Path):
        self.temp_root = temp_root
        self.process: subprocess.Popen[str] | None = None

    def __enter__(self) -> StdioProcess:
        db_path = self.temp_root / "codex_agent_mem.db"
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPYCACHEPREFIX"] = str(self.temp_root / "pycache")
        env["PYTHONPATH"] = (
            str(SRC_DIR)
            if not env.get("PYTHONPATH")
            else str(SRC_DIR) + os.pathsep + env["PYTHONPATH"]
        )
        command = [
            sys.executable,
            "-m",
            "codex_agent_mem.mcp_stdio",
            "--db-path",
            str(db_path),
            "--profile",
            "full",
            "--response-mode",
            "compact",
            "--cache-ttl-seconds",
            "0",
            "--runtime-log-dir",
            str(self.temp_root / "runtime"),
            "--idle-timeout-seconds",
            "0",
        ]
        self.process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        return self

    def __exit__(self, exc_type: object, _exc: object, _tb: object) -> None:
        if self.process is None:
            return
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
            if exc_type is None:
                raise SmokeFailure("stdio subprocess did not exit after stdin closed")
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()
        if exc_type is None and self.process.returncode not in (0, None):
            raise SmokeFailure(
                f"stdio subprocess exited with {self.process.returncode}"
            )

    def request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise SmokeFailure("stdio subprocess is not running")
        self.process.stdin.write(json.dumps(message, ensure_ascii=True) + "\n")
        self.process.stdin.flush()
        line = self._readline_with_timeout(timeout=10)
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr is not None else ""
            raise SmokeFailure(f"stdio subprocess closed stdout: {stderr.strip()[:1000]}")
        return json.loads(line)

    def _readline_with_timeout(self, *, timeout: float) -> str:
        if self.process is None or self.process.stdout is None:
            raise SmokeFailure("stdio subprocess stdout is unavailable")
        output: queue.Queue[str] = queue.Queue(maxsize=1)

        def read_line() -> None:
            output.put(self.process.stdout.readline())

        thread = threading.Thread(target=read_line, daemon=True)
        thread.start()
        try:
            return output.get(timeout=timeout)
        except queue.Empty as exc:
            if self.process.poll() is None:
                self.process.kill()
            stderr = self.process.stderr.read() if self.process.stderr is not None else ""
            raise SmokeFailure(
                f"timed out waiting for stdio response: {stderr.strip()[:1000]}"
            ) from exc


def _run_subprocess(temp_root: Path) -> None:
    db_path = temp_root / "codex_agent_mem.db"
    workspace = temp_root / "workspace"
    workspace.mkdir()
    store = CodexAgentMemStore(db_path)
    try:
        _seed_store(store, workspace)
    finally:
        store.close()
    with StdioProcess(temp_root) as client:
        contract_state = _exercise_contract(client.request, temp_root=temp_root)
    with StdioProcess(temp_root) as later_client:
        _exercise_later_process_retrieval(
            later_client.request,
            temp_root=temp_root,
            note_phrase=str(contract_state["note_phrase"]),
            scoped_session_id=int(contract_state["scoped_session_id"]),
            note_observation_id=int(contract_state["note_observation_id"]),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the codex-agent-mem MCP contract.")
    parser.add_argument(
        "--subprocess",
        action="store_true",
        help="Exercise the real stdio process instead of the in-process server object.",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Run both the in-process and stdio subprocess contract checks.",
    )
    args = parser.parse_args(argv)
    modes = (
        ["in-process", "subprocess"]
        if args.both
        else ["subprocess" if args.subprocess else "in-process"]
    )

    try:
        for mode in modes:
            with tempfile.TemporaryDirectory(prefix=f"codex-agent-mem-{mode}-") as tmp:
                temp_root = Path(tmp)
                if mode == "subprocess":
                    _run_subprocess(temp_root)
                else:
                    _run_in_process(temp_root)
                print(f"PASS: MCP contract smoke ({mode})")
    except SmokeFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
