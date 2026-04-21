from __future__ import annotations

import argparse
import json
import signal
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


def _make_handler(server: CodexAgentMemMCPServer, runtime: MCPRuntimeState) -> type[BaseHTTPRequestHandler]:
    class DaemonHandler(BaseHTTPRequestHandler):
        server_version = "codex-agent-mem-daemon/1.0"

        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/health":
                self.send_error(404)
                return
            self._write_json(runtime.snapshot())

        def do_POST(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/mcp":
                self.send_error(404)
                return
            content_length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(content_length)
            try:
                message = json.loads(raw.decode("utf-8"))
                response = server.handle_request(message)
            except Exception as exc:  # pragma: no cover - defensive runtime path
                response = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(exc)}}
            if response is None:
                self.send_response(204)
                self.end_headers()
                return
            self._write_json(response)

        def log_message(self, _format: str, *args: Any) -> None:
            return

        def _write_json(self, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return DaemonHandler


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an optional local codex-agent-mem MCP daemon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=37773)
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
    httpd = ThreadingHTTPServer((args.host, args.port), _make_handler(mcp_server, runtime))
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
