from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codex_agent_mem import __version__
from codex_agent_mem.config import AppConfig
from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import now_iso


_EOF = object()


@dataclass
class MCPRuntimeState:
    db_path: Path
    idle_timeout_seconds: int | None
    pid: int = field(default_factory=os.getpid)
    ppid: int = field(default_factory=os.getppid)
    started_at: str = field(default_factory=now_iso)
    requests_count: int = 0
    last_request_ts: str | None = None
    last_request_method: str | None = None
    last_tool_name: str | None = None
    exit_reason: str = "running"
    _started_perf: float = field(default_factory=time.monotonic, repr=False)
    _last_request_perf: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self._last_request_perf = self._started_perf

    def note_request(self, method: str, tool_name: str | None = None) -> None:
        now_perf = time.monotonic()
        now_ts = now_iso()
        with self._lock:
            self.requests_count += 1
            self.last_request_ts = now_ts
            self.last_request_method = method
            self.last_tool_name = tool_name
            self._last_request_perf = now_perf

    def set_exit_reason(self, reason: str) -> None:
        with self._lock:
            if self.exit_reason == "running":
                self.exit_reason = reason

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now_perf = time.monotonic()
            idle_seconds = round(now_perf - self._last_request_perf, 3) if self._last_request_perf is not None else None
            return {
                "pid": self.pid,
                "ppid": self.ppid,
                "db_path": str(self.db_path),
                "protocol": "stdio",
                "connection_model": "one_process_per_connection",
                "server_version": __version__,
                "started_at": self.started_at,
                "uptime_seconds": round(now_perf - self._started_perf, 3),
                "requests_count": self.requests_count,
                "last_request_ts": self.last_request_ts,
                "last_request_method": self.last_request_method,
                "last_tool_name": self.last_tool_name,
                "idle_seconds": idle_seconds,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "exit_reason": self.exit_reason,
            }

    def should_exit_for_idle(self) -> bool:
        if self.idle_timeout_seconds is None:
            return False
        if self._last_request_perf is None:
            return False
        return (time.monotonic() - self._last_request_perf) >= self.idle_timeout_seconds


def _runtime_log(event: str, **fields: Any) -> None:
    payload = {
        "source": "codex-agent-mem.mcp_stdio",
        "event": event,
        "ts": now_iso(),
        **fields,
    }
    sys.stderr.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stderr.flush()


class CodexAgentMemMCPServer:
    def __init__(self, store: CodexAgentMemStore, runtime: MCPRuntimeState):
        self.store = store
        self.runtime = runtime
        self.protocol_version = "2025-06-18"

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "mem_search",
                "description": "Search stored codex-agent-mem observations for a project or across all projects.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "project_key": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "mem_get",
                "description": "Get one stored observation by id.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "observation_id": {"type": "integer", "minimum": 1},
                    },
                    "required": ["observation_id"],
                },
            },
            {
                "name": "mem_recent",
                "description": "Return recent observations, optionally scoped to one project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                },
            },
            {
                "name": "mem_project_brief",
                "description": "Return a compact brief for one project: counts, recent observations, and recent decisions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_open_work",
                "description": "Return deterministic open work for one project: pending items, blockers, Definition of Done gaps, and closure guardrails.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_completion_check",
                "description": "Return a deterministic closure check for one project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_recent_changes",
                "description": "Return changes since the last stable context sync: new pending items, resolved work, blocker changes, DoD gap changes, and new decisions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_scope_guard",
                "description": "Return compact scope guardrails for one project: constraints, must-not-drop items, and closure conflicts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_context_pack",
                "description": "Return a compact continuity pack optimized to carry project context forward with fewer tokens.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "budget": {"type": "string", "enum": ["auto", "micro", "normal", "full"]},
                        "max_chars": {"type": "integer", "minimum": 400, "maximum": 6000},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_provenance",
                "description": "Return audit provenance for one stored observation, including the original turn context.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "observation_id": {"type": "integer", "minimum": 1},
                    },
                    "required": ["observation_id"],
                },
            },
            {
                "name": "mem_health",
                "description": "Return a deterministic health report for one project: duplicates, contradictions, stale items, DoD coverage, and suggestions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_health_runtime",
                "description": "Return runtime health for this stdio MCP process: pid, uptime, idle timeout, request counts, and exit diagnostics.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "mem_snapshot_list",
                "description": "List stored memory snapshots for one project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_snapshot_create",
                "description": "Create a versioned memory snapshot for one project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "label": {"type": "string"},
                    },
                    "required": ["project_key", "label"],
                },
            },
            {
                "name": "mem_snapshot_restore",
                "description": "Restore one stored snapshot into the generated AGENTS.md continuity block when the project root path is known.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "snapshot_id": {"type": "integer", "minimum": 1},
                    },
                    "required": ["project_key", "snapshot_id"],
                },
            },
            {
                "name": "mem_policy_list",
                "description": "List active and inactive memory policies for one project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_policy_validate",
                "description": "Validate one memory policy definition before adding it.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "policy_kind": {"type": "string"},
                        "rule": {"type": "object"},
                    },
                    "required": ["policy_kind", "rule"],
                },
            },
            {
                "name": "mem_policy_add",
                "description": "Add one memory policy to a project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "policy_kind": {"type": "string"},
                        "rule": {"type": "object"},
                        "enabled": {"type": "boolean"},
                    },
                    "required": ["project_key", "policy_kind", "rule"],
                },
            },
            {
                "name": "mem_policy_remove",
                "description": "Remove one memory policy from a project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "policy_id": {"type": "integer", "minimum": 1},
                    },
                    "required": ["project_key", "policy_id"],
                },
            },
            {
                "name": "mem_inheritance_list",
                "description": "List inheritance links for one project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_inheritance_add",
                "description": "Add one inheritance link to a project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "source_project_key": {"type": "string"},
                        "mode": {"type": "string"},
                        "selector": {"type": "object"},
                        "enabled": {"type": "boolean"},
                    },
                    "required": ["project_key", "source_project_key", "mode"],
                },
            },
            {
                "name": "mem_inheritance_remove",
                "description": "Remove one inheritance link from a project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "inheritance_id": {"type": "integer", "minimum": 1},
                    },
                    "required": ["project_key", "inheritance_id"],
                },
            },
            {
                "name": "mem_repair_propose",
                "description": "Return governed repair proposals based on the latest health report for a project.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                    "required": ["project_key"],
                },
            },
            {
                "name": "mem_repair_apply",
                "description": "Apply one supported repair proposal as a derived repair event.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "repair_kind": {"type": "string"},
                        "health_report_id": {"type": "integer", "minimum": 1},
                    },
                    "required": ["project_key", "repair_kind"],
                },
            },
        ]

    def _tool_result(self, data: Any, is_error: bool = False) -> dict[str, Any]:
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": data,
            "isError": is_error,
        }

    def handle_request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}
        tool_name = params.get("name") if method == "tools/call" else None

        if method in {"initialized", "notifications/initialized"}:
            return None
        if method:
            self.runtime.note_request(str(method), str(tool_name) if tool_name else None)
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "codex-agent-mem", "version": __version__},
                },
            }
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": self.list_tools()}}
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            try:
                if name == "mem_search":
                    data = self.store.search_observations(
                        query=arguments.get("query", ""),
                        project_key=arguments.get("project_key"),
                        limit=int(arguments.get("limit", 10)),
                    )
                elif name == "mem_get":
                    data = self.store.get_observation(int(arguments["observation_id"]))
                    if data is None:
                        raise ValueError("Observation not found")
                elif name == "mem_recent":
                    data = self.store.recent_observations(
                        project_key=arguments.get("project_key"),
                        limit=int(arguments.get("limit", 10)),
                    )
                elif name == "mem_project_brief":
                    data = self.store.project_brief(arguments["project_key"])
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_open_work":
                    data = self.store.open_work_report(arguments["project_key"])
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_completion_check":
                    data = self.store.completion_check(arguments["project_key"], record=True)
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_recent_changes":
                    data = self.store.recent_changes(arguments["project_key"])
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_scope_guard":
                    data = self.store.scope_guard(arguments["project_key"])
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_context_pack":
                    data = self.store.context_pack(
                        arguments["project_key"],
                        budget=str(arguments.get("budget", "auto")),
                        max_chars=int(arguments["max_chars"]) if arguments.get("max_chars") is not None else None,
                    )
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_provenance":
                    data = self.store.get_provenance(
                        memory_id=int(arguments["observation_id"]),
                        memory_kind="observation",
                    )
                    if data is None:
                        raise ValueError("Provenance not found")
                elif name == "mem_health":
                    data = self.store.health_report(arguments["project_key"], record=False)
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_health_runtime":
                    data = self.runtime.snapshot()
                elif name == "mem_snapshot_list":
                    data = self.store.list_snapshots(
                        arguments["project_key"],
                        limit=int(arguments.get("limit", 20)),
                    )
                elif name == "mem_snapshot_create":
                    data = self.store.snapshot_create(
                        arguments["project_key"],
                        label=str(arguments["label"]),
                    )
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_snapshot_restore":
                    data = self.store.snapshot_restore(
                        arguments["project_key"],
                        int(arguments["snapshot_id"]),
                    )
                    if data is None:
                        raise ValueError("Snapshot not found")
                elif name == "mem_policy_list":
                    data = self.store.list_policies(arguments["project_key"])
                elif name == "mem_policy_validate":
                    data = self.store.validate_policy(
                        str(arguments["policy_kind"]),
                        arguments.get("rule") or {},
                    )
                elif name == "mem_policy_add":
                    data = self.store.add_policy(
                        arguments["project_key"],
                        str(arguments["policy_kind"]),
                        arguments.get("rule") or {},
                        enabled=bool(arguments.get("enabled", True)),
                    )
                elif name == "mem_policy_remove":
                    data = self.store.remove_policy(
                        arguments["project_key"],
                        int(arguments["policy_id"]),
                    )
                elif name == "mem_inheritance_list":
                    data = self.store.list_inheritances(arguments["project_key"])
                elif name == "mem_inheritance_add":
                    data = self.store.add_inheritance(
                        arguments["project_key"],
                        str(arguments["source_project_key"]),
                        str(arguments["mode"]),
                        arguments.get("selector") or {},
                        enabled=bool(arguments.get("enabled", True)),
                    )
                elif name == "mem_inheritance_remove":
                    data = self.store.remove_inheritance(
                        arguments["project_key"],
                        int(arguments["inheritance_id"]),
                    )
                elif name == "mem_repair_propose":
                    data = self.store._repair_proposals_from_health(arguments["project_key"])
                elif name == "mem_repair_apply":
                    data = self.store.apply_repair(
                        arguments["project_key"],
                        str(arguments["repair_kind"]),
                        int(arguments["health_report_id"]) if arguments.get("health_report_id") is not None else None,
                    )
                else:
                    raise ValueError(f"Unknown tool: {name}")
                return {"jsonrpc": "2.0", "id": msg_id, "result": self._tool_result(data)}
            except Exception as exc:
                return {"jsonrpc": "2.0", "id": msg_id, "result": self._tool_result({"error": str(exc)}, is_error=True)}
        if msg_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        return None


def _configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", newline="\n")


def _write_response(message: dict[str, Any]) -> None:
    # Keep the wire ASCII-safe on Windows consoles; JSON consumers still recover
    # the original Unicode content via escaped sequences.
    sys.stdout.write(json.dumps(message, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _stdin_reader(out_queue: queue.Queue[Any], stop_event: threading.Event) -> None:
    try:
        for line in sys.stdin:
            if stop_event.is_set():
                break
            out_queue.put(line)
    except Exception as exc:  # pragma: no cover - defensive runtime path
        out_queue.put(("reader_error", str(exc)))
    finally:
        out_queue.put(_EOF)


def _install_signal_handlers(runtime: MCPRuntimeState, stop_event: threading.Event) -> None:
    def _handler(signum: int, _frame: object) -> None:
        signame = signal.Signals(signum).name.lower()
        runtime.set_exit_reason(f"signal_{signame}")
        _runtime_log(
            "signal",
            pid=runtime.pid,
            ppid=runtime.ppid,
            signal=signame,
            db_path=str(runtime.db_path),
        )
        stop_event.set()

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError, RuntimeError):  # pragma: no cover - platform dependent
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the codex-agent-mem MCP stdio server")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    parser.add_argument(
        "--idle-timeout-seconds",
        type=int,
        default=300,
        help="Defensive shutdown after this much MCP inactivity. Use 0 to disable.",
    )
    args = parser.parse_args(argv)
    _configure_stdio()
    stop_event = threading.Event()
    runtime = MCPRuntimeState(
        db_path=args.db_path,
        idle_timeout_seconds=args.idle_timeout_seconds if args.idle_timeout_seconds > 0 else None,
    )
    _install_signal_handlers(runtime, stop_event)
    store = CodexAgentMemStore(args.db_path)
    server = CodexAgentMemMCPServer(store, runtime)
    input_queue: queue.Queue[Any] = queue.Queue()
    reader = threading.Thread(target=_stdin_reader, args=(input_queue, stop_event), daemon=True)
    reader.start()
    _runtime_log(
        "start",
        pid=runtime.pid,
        ppid=runtime.ppid,
        db_path=str(args.db_path),
        idle_timeout_seconds=runtime.idle_timeout_seconds,
    )
    try:
        while not stop_event.is_set():
            try:
                item = input_queue.get(timeout=0.25)
            except queue.Empty:
                if runtime.should_exit_for_idle():
                    runtime.set_exit_reason("idle_timeout")
                    break
                continue
            if item is _EOF:
                runtime.set_exit_reason("stdin_eof")
                break
            if isinstance(item, tuple) and item and item[0] == "reader_error":
                runtime.set_exit_reason("stdin_reader_error")
                _runtime_log(
                    "reader_error",
                    pid=runtime.pid,
                    ppid=runtime.ppid,
                    db_path=str(args.db_path),
                    error=item[1],
                )
                break
            line = str(item).strip()
            if not line:
                continue
            try:
                message = json.loads(line)
                response = server.handle_request(message)
                if response is not None:
                    _write_response(response)
            except Exception as exc:
                err = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(exc)}}
                _write_response(err)
    finally:
        stop_event.set()
        runtime_snapshot = runtime.snapshot()
        try:
            store.close()
        finally:
            _runtime_log("exit", **runtime_snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
