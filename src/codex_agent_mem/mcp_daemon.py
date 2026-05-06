from __future__ import annotations

import argparse
import hmac
import ipaddress
import json
import signal
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from codex_agent_mem.config import AppConfig
from codex_agent_mem.mcp_stdio import (
    CodexAgentMemMCPServer,
    HeartbeatRegistry,
    LazyStoreProvider,
    MCPRuntimeState,
    RuntimeTelemetry,
    _runtime_log,
)


_REMOTE_BIND_ERROR = (
    "Remote daemon bind is not supported in the public local-first core. "
    "Use 127.0.0.1, localhost, or ::1."
)


def _validate_bind_host(host: str) -> str:
    normalized = (host or "").strip()
    if normalized.casefold() == "localhost":
        return normalized
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError(_REMOTE_BIND_ERROR) from exc
    if address in {ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")}:
        return normalized
    raise ValueError(_REMOTE_BIND_ERROR)


def _validate_auth_token(auth_token: str | None) -> str | None:
    if auth_token is None:
        return None
    if auth_token == "":
        raise ValueError("--auth-token cannot be empty.")
    return auth_token


def _public_health_snapshot(runtime: MCPRuntimeState) -> dict[str, Any]:
    snapshot = runtime.snapshot()
    return {
        key: snapshot[key]
        for key in (
            "pid",
            "ppid",
            "protocol",
            "connection_model",
            "server_version",
            "profile",
            "read_only",
            "response_mode",
            "lazy_initialized",
            "cache_ttl_seconds",
            "cache_hits",
            "cache_misses",
            "same_db_process_count",
            "spawn_storm_warning",
            "telemetry_mode",
            "started_at",
            "uptime_seconds",
            "requests_count",
            "last_request_ts",
            "last_request_method",
            "last_tool_name",
            "idle_seconds",
            "idle_timeout_seconds",
            "exit_reason",
        )
        if key in snapshot
    }


def _server_class_for_host(host: str) -> type[ThreadingHTTPServer]:
    if host == "::1":
        class ThreadingHTTPServerV6(ThreadingHTTPServer):
            address_family = socket.AF_INET6
            daemon_threads = True

        return ThreadingHTTPServerV6

    class LocalThreadingHTTPServer(ThreadingHTTPServer):
        daemon_threads = True

    return LocalThreadingHTTPServer


def _make_handler(
    server: CodexAgentMemMCPServer,
    runtime: MCPRuntimeState,
    *,
    auth_token: str | None = None,
) -> type[BaseHTTPRequestHandler]:
    request_lock = threading.RLock()
    expected_authorization = f"Bearer {auth_token}" if auth_token is not None else None

    class DaemonHandler(BaseHTTPRequestHandler):
        server_version = "codex-agent-mem-daemon/1.0"

        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/health":
                self.send_error(404)
                return
            self._write_json(_public_health_snapshot(runtime))

        def do_POST(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/mcp":
                self.send_error(404)
                return
            if not self._is_authorized():
                self._discard_request_body()
                self._write_json({"error": "unauthorized"}, status=401)
                return
            content_length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(content_length)
            try:
                message = json.loads(raw.decode("utf-8"))
                # The daemon shares one MCP server/store across handler threads.
                # Serialize request handling so SQLite access stays deterministic.
                with request_lock:
                    response = server.handle_request(message)
            except Exception as exc:  # pragma: no cover - defensive runtime path
                response = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(exc)}}
            if response is None:
                self.send_response(204)
                self.send_header("Connection", "close")
                self.close_connection = True
                self.end_headers()
                return
            self._write_json(response)

        def log_message(self, _format: str, *args: Any) -> None:
            return

        def _is_authorized(self) -> bool:
            if expected_authorization is None:
                return True
            supplied_authorization = self.headers.get("Authorization", "")
            return hmac.compare_digest(supplied_authorization, expected_authorization)

        def _discard_request_body(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0") or 0)
            if content_length > 0:
                self.rfile.read(content_length)

        def _write_json(self, payload: Any, *, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()

    return DaemonHandler


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an optional local codex-agent-mem MCP daemon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=37773)
    parser.add_argument("--auth-token", default=None, help="Optional bearer token required for /mcp requests.")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--profile", choices=["minimal", "standard", "full"], default="full")
    parser.add_argument("--response-mode", choices=["compact", "balanced", "verbose"], default="compact")
    parser.add_argument("--cache-ttl-seconds", type=int, default=15)
    parser.add_argument("--telemetry-mode", choices=["off", "summary", "debug"], default="off")
    parser.add_argument("--runtime-log-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        args.host = _validate_bind_host(args.host)
        args.auth_token = _validate_auth_token(args.auth_token)
    except ValueError as exc:
        parser.error(str(exc))
    runtime = MCPRuntimeState(
        db_path=args.db_path,
        idle_timeout_seconds=None,
        profile=args.profile,
        read_only=bool(args.read_only),
        response_mode=args.response_mode,
        cache_ttl_seconds=max(0, args.cache_ttl_seconds),
        telemetry_mode=args.telemetry_mode,
    )
    runtime.heartbeat = HeartbeatRegistry(args.db_path, runtime_dir=args.runtime_log_dir)
    runtime.telemetry = RuntimeTelemetry(args.telemetry_mode, log_dir=args.runtime_log_dir)
    runtime.write_heartbeat()
    provider = LazyStoreProvider(args.db_path, runtime)
    mcp_server = CodexAgentMemMCPServer(provider, runtime)
    httpd = _server_class_for_host(args.host)(
        (args.host, args.port),
        _make_handler(mcp_server, runtime, auth_token=args.auth_token),
    )
    stop_event = threading.Event()

    def _stop(signum: int, _frame: object) -> None:
        signame = signal.Signals(signum).name.lower()
        runtime.set_exit_reason(f"signal_{signame}")
        stop_event.set()
        httpd.shutdown()

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, _stop)

    _runtime_log(
        "daemon_start",
        pid=runtime.pid,
        ppid=runtime.ppid,
        host=args.host,
        port=args.port,
        db_path=str(args.db_path),
        profile=runtime.profile,
        read_only=runtime.read_only,
    )
    if runtime.telemetry is not None:
        runtime.telemetry.emit(
            "process_start",
            pid=runtime.pid,
            ppid=runtime.ppid,
            protocol="http-daemon",
            host=args.host,
            port=args.port,
            db_path=str(args.db_path),
        )
    try:
        httpd.serve_forever()
    finally:
        if not stop_event.is_set():
            runtime.set_exit_reason("server_stop")
        snapshot = runtime.snapshot()
        provider.close()
        httpd.server_close()
        if runtime.telemetry is not None:
            runtime.telemetry.emit("process_exit", **snapshot)
        _runtime_log("daemon_exit", **snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
