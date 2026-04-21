from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codex_agent_mem import __version__
from codex_agent_mem.config import AppConfig
from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import now_iso
from codex_agent_mem.runtime_efficiency import (
    HeartbeatRegistry,
    RuntimeTelemetry,
    ShortTTLCache,
    compact_text_summary,
    stable_hash,
)


_EOF = object()

PROFILE_TOOLS: dict[str, set[str]] = {
    "minimal": {
        "mem_context_pack",
        "mem_open_work",
        "mem_completion_check",
        "mem_health_runtime",
    },
    "standard": {
        "mem_context_pack",
        "mem_open_work",
        "mem_completion_check",
        "mem_health_runtime",
        "mem_search",
        "mem_get",
        "mem_recent",
        "mem_project_brief",
        "mem_recent_changes",
        "mem_scope_guard",
        "mem_health",
        "mem_provenance",
        "mem_snapshot_list",
        "mem_policy_list",
        "mem_policy_validate",
        "mem_inheritance_list",
        "mem_repair_propose",
    },
}

MUTATING_TOOLS = {
    "mem_snapshot_create",
    "mem_snapshot_restore",
    "mem_policy_add",
    "mem_policy_remove",
    "mem_inheritance_add",
    "mem_inheritance_remove",
    "mem_repair_apply",
}

CACHEABLE_TOOLS = {
    "mem_context_pack",
    "mem_project_brief",
    "mem_open_work",
    "mem_scope_guard",
}


@dataclass
class MCPRuntimeState:
    db_path: Path
    idle_timeout_seconds: int | None
    profile: str = "full"
    read_only: bool = False
    response_mode: str = "compact"
    cache_ttl_seconds: int = 15
    telemetry_mode: str = "off"
    pid: int = field(default_factory=os.getpid)
    ppid: int = field(default_factory=os.getppid)
    started_at: str = field(default_factory=now_iso)
    requests_count: int = 0
    last_request_ts: str | None = None
    last_request_method: str | None = None
    last_tool_name: str | None = None
    exit_reason: str = "running"
    lazy_initialized: bool = False
    cache_hits: int = 0
    cache_misses: int = 0
    same_db_process_count: int = 1
    spawn_storm_warning: bool = False
    heartbeat: HeartbeatRegistry | None = field(default=None, repr=False)
    telemetry: RuntimeTelemetry | None = field(default=None, repr=False)
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
        self.write_heartbeat()
        if self.telemetry is not None:
            event = "tool_call" if method == "tools/call" else method.replace("/", "_")
            self.telemetry.emit(event, pid=self.pid, method=method, tool_name=tool_name)

    def set_exit_reason(self, reason: str) -> None:
        with self._lock:
            if self.exit_reason == "running":
                self.exit_reason = reason

    def mark_lazy_initialized(self) -> None:
        with self._lock:
            self.lazy_initialized = True

    def set_cache_stats(self, hits: int, misses: int) -> None:
        with self._lock:
            self.cache_hits = hits
            self.cache_misses = misses

    def write_heartbeat(self) -> None:
        if self.heartbeat is None:
            return
        try:
            self.heartbeat.write(
                profile=self.profile,
                read_only=self.read_only,
                response_mode=self.response_mode,
                started_at=self.started_at,
            )
        except OSError:
            return

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now_perf = time.monotonic()
            idle_seconds = round(now_perf - self._last_request_perf, 3) if self._last_request_perf is not None else None
            same_db_process_count = self.same_db_process_count
            if self.heartbeat is not None:
                try:
                    self.heartbeat.write(
                        profile=self.profile,
                        read_only=self.read_only,
                        response_mode=self.response_mode,
                        started_at=self.started_at,
                    )
                    same_db_process_count = self.heartbeat.count_recent()
                    self.same_db_process_count = same_db_process_count
                    self.spawn_storm_warning = same_db_process_count >= 5
                except OSError:
                    pass
            return {
                "pid": self.pid,
                "ppid": self.ppid,
                "db_path": str(self.db_path),
                "protocol": "stdio",
                "connection_model": "one_process_per_connection",
                "server_version": __version__,
                "profile": self.profile,
                "read_only": self.read_only,
                "response_mode": self.response_mode,
                "lazy_initialized": self.lazy_initialized,
                "cache_ttl_seconds": self.cache_ttl_seconds,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "same_db_process_count": same_db_process_count,
                "spawn_storm_warning": self.spawn_storm_warning,
                "telemetry_mode": self.telemetry_mode,
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


class StoreProvider:
    def get(self) -> CodexAgentMemStore:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class EagerStoreProvider(StoreProvider):
    def __init__(self, store: CodexAgentMemStore):
        self._store = store

    def get(self) -> CodexAgentMemStore:
        return self._store

    def close(self) -> None:
        return None


class LazyStoreProvider(StoreProvider):
    def __init__(self, db_path: Path, runtime: MCPRuntimeState):
        self.db_path = db_path
        self.runtime = runtime
        self._store: CodexAgentMemStore | None = None
        self._lock = threading.Lock()

    def get(self) -> CodexAgentMemStore:
        with self._lock:
            if self._store is None:
                self._store = CodexAgentMemStore(self.db_path)
                if self.runtime.read_only:
                    self._store.set_query_only(True)
                self.runtime.mark_lazy_initialized()
                if self.runtime.telemetry is not None:
                    self.runtime.telemetry.emit(
                        "store_open",
                        pid=self.runtime.pid,
                        db_path=str(self.db_path),
                        read_only=self.runtime.read_only,
                    )
            return self._store

    def close(self) -> None:
        with self._lock:
            if self._store is not None:
                self._store.close()
                self._store = None


class CodexAgentMemMCPServer:
    def __init__(
        self,
        store: CodexAgentMemStore | StoreProvider,
        runtime: MCPRuntimeState,
    ):
        self._store_provider = store if isinstance(store, StoreProvider) else EagerStoreProvider(store)
        self.runtime = runtime
        self.protocol_version = "2025-06-18"
        self.cache = ShortTTLCache(ttl_seconds=runtime.cache_ttl_seconds)
        if not isinstance(store, StoreProvider) and runtime.read_only:
            store.set_query_only(True)

    @property
    def store(self) -> CodexAgentMemStore:
        return self._store_provider.get()

    def list_tools(self) -> list[dict[str, Any]]:
        tools = [
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
                        "known_pack_hash": {"type": "string"},
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
        allowed_tools = PROFILE_TOOLS.get(self.runtime.profile)
        if allowed_tools is None:
            return tools
        return [tool for tool in tools if str(tool["name"]) in allowed_tools]

    def _tool_result(self, data: Any, is_error: bool = False) -> dict[str, Any]:
        if self.runtime.response_mode == "verbose":
            text = json.dumps(data, ensure_ascii=False, indent=2)
        elif self.runtime.response_mode == "balanced":
            summary = compact_text_summary(data, is_error=is_error)
            text = f"{summary}\nstructuredContent contains the complete payload."
        else:
            text = compact_text_summary(data, is_error=is_error)
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": data,
            "isError": is_error,
        }

    def _cache_key(self, tool_name: str, arguments: dict[str, Any], revision: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "tool": tool_name,
            "arguments": arguments,
            "revision": revision,
            "profile": self.runtime.profile,
        }

    def _project_revision(self, project_key: str) -> dict[str, Any] | None:
        return self.store.project_revision(project_key)

    def _cached_call(self, tool_name: str, arguments: dict[str, Any], factory: Any) -> Any:
        if tool_name not in CACHEABLE_TOOLS:
            return factory()
        project_key = str(arguments["project_key"])
        revision = self._project_revision(project_key)
        cache_key = self._cache_key(tool_name, arguments, revision)
        cached = self.cache.get(cache_key)
        if cached is not None:
            self.runtime.set_cache_stats(self.cache.stats.hits, self.cache.stats.misses)
            return cached
        data = factory()
        self.cache.set(cache_key, data)
        self.runtime.set_cache_stats(self.cache.stats.hits, self.cache.stats.misses)
        return data

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
                listed_tools = {tool["name"] for tool in self.list_tools()}
                if name not in listed_tools:
                    raise ValueError(f"Tool unavailable in profile '{self.runtime.profile}': {name}")
                if self.runtime.read_only and name in MUTATING_TOOLS:
                    raise PermissionError(f"Tool is disabled in read-only mode: {name}")
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
                    data = self._cached_call(
                        name,
                        arguments,
                        lambda: self.store.project_brief(arguments["project_key"]),
                    )
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_open_work":
                    data = self._cached_call(
                        name,
                        arguments,
                        lambda: self.store.open_work_report(arguments["project_key"]),
                    )
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_completion_check":
                    data = self.store.completion_check(arguments["project_key"], record=not self.runtime.read_only)
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_recent_changes":
                    data = self.store.recent_changes(arguments["project_key"])
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_scope_guard":
                    data = self._cached_call(
                        name,
                        arguments,
                        lambda: self.store.scope_guard(arguments["project_key"]),
                    )
                    if data is None:
                        raise ValueError("Project not found")
                elif name == "mem_context_pack":
                    data = self._cached_call(
                        name,
                        arguments,
                        lambda: self.store.context_pack(
                            arguments["project_key"],
                            budget=str(arguments.get("budget", "auto")),
                            max_chars=int(arguments["max_chars"]) if arguments.get("max_chars") is not None else None,
                        ),
                    )
                    if data is None:
                        raise ValueError("Project not found")
                    stats = dict(data.get("stats") or {})
                    stats.pop("build_ms", None)
                    pack_hash = stable_hash(
                        {
                            "text": data.get("text"),
                            "stats": stats,
                            "project_key": arguments["project_key"],
                        }
                    )
                    known_pack_hash = arguments.get("known_pack_hash")
                    if known_pack_hash and str(known_pack_hash) == pack_hash:
                        data = {
                            "not_modified": True,
                            "pack_hash": pack_hash,
                            "message": "continuity pack unchanged",
                        }
                    elif isinstance(data, dict):
                        data = dict(data)
                        data["pack_hash"] = pack_hash
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
                    data = self.store._repair_proposals_from_health(
                        arguments["project_key"],
                        record_if_missing=not self.runtime.read_only,
                    )
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


def _forward_to_daemon(daemon_url: str, message: dict[str, Any]) -> dict[str, Any] | None:
    body = json.dumps(message, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        daemon_url.rstrip("/") + "/mcp",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status == 204:
                return None
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if raw:
            return json.loads(raw)
        raise
    return json.loads(raw)


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
        if runtime.telemetry is not None:
            runtime.telemetry.emit("signal", pid=runtime.pid, signal=signame, db_path=str(runtime.db_path))
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
    parser.add_argument("--read-only", action="store_true", help="Disable mutating MCP tools and closure writes.")
    parser.add_argument(
        "--profile",
        choices=["minimal", "standard", "full"],
        default="full",
        help="Limit exposed MCP tools. Use minimal for low-impact Desktop configs.",
    )
    parser.add_argument(
        "--response-mode",
        choices=["compact", "balanced", "verbose"],
        default="compact",
        help="Control MCP content.text verbosity. structuredContent always carries the full payload.",
    )
    parser.add_argument(
        "--cache-ttl-seconds",
        type=int,
        default=15,
        help="Short in-process cache TTL for expensive read tools. Use 0 to disable.",
    )
    parser.add_argument(
        "--telemetry-mode",
        choices=["off", "summary", "debug"],
        default="off",
        help="Write local runtime events.jsonl metadata. Debug is never the default.",
    )
    parser.add_argument(
        "--runtime-log-dir",
        type=Path,
        default=None,
        help="Directory for heartbeat and optional events.jsonl runtime metadata.",
    )
    parser.add_argument(
        "--daemon-url",
        default=None,
        help="Forward stdio JSON-RPC requests to an already running codex-agent-mem daemon.",
    )
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
        profile=args.profile,
        read_only=bool(args.read_only),
        response_mode=args.response_mode,
        cache_ttl_seconds=max(0, args.cache_ttl_seconds),
        telemetry_mode=args.telemetry_mode,
    )
    runtime.heartbeat = HeartbeatRegistry(args.db_path, runtime_dir=args.runtime_log_dir)
    runtime.telemetry = RuntimeTelemetry(args.telemetry_mode, log_dir=args.runtime_log_dir)
    runtime.write_heartbeat()
    _install_signal_handlers(runtime, stop_event)
    store_provider: LazyStoreProvider | None = None
    server: CodexAgentMemMCPServer | None = None
    if args.daemon_url is None:
        store_provider = LazyStoreProvider(args.db_path, runtime)
        server = CodexAgentMemMCPServer(store_provider, runtime)
    input_queue: queue.Queue[Any] = queue.Queue()
    reader = threading.Thread(target=_stdin_reader, args=(input_queue, stop_event), daemon=True)
    reader.start()
    _runtime_log(
        "start",
        pid=runtime.pid,
        ppid=runtime.ppid,
        db_path=str(args.db_path),
        idle_timeout_seconds=runtime.idle_timeout_seconds,
        profile=runtime.profile,
        read_only=runtime.read_only,
        response_mode=runtime.response_mode,
        daemon_url=args.daemon_url,
    )
    if runtime.telemetry is not None:
        runtime.telemetry.emit(
            "process_start",
            pid=runtime.pid,
            ppid=runtime.ppid,
            db_path=str(args.db_path),
            profile=runtime.profile,
            read_only=runtime.read_only,
            response_mode=runtime.response_mode,
        )
    try:
        while not stop_event.is_set():
            try:
                item = input_queue.get(timeout=0.25)
            except queue.Empty:
                if runtime.should_exit_for_idle():
                    runtime.set_exit_reason("idle_timeout")
                    if runtime.telemetry is not None:
                        runtime.telemetry.emit("idle_timeout", pid=runtime.pid, db_path=str(args.db_path))
                    break
                continue
            if item is _EOF:
                runtime.set_exit_reason("stdin_eof")
                if runtime.telemetry is not None:
                        runtime.telemetry.emit("stdin_eof", pid=runtime.pid, db_path=str(args.db_path))
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
                response = (
                    _forward_to_daemon(args.daemon_url, message)
                    if args.daemon_url is not None
                    else server.handle_request(message)
                )
                if response is not None:
                    _write_response(response)
            except Exception as exc:
                err = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(exc)}}
                _write_response(err)
    finally:
        stop_event.set()
        runtime_snapshot = runtime.snapshot()
        try:
            if store_provider is not None:
                store_provider.close()
        finally:
            if runtime.telemetry is not None:
                runtime.telemetry.emit("process_exit", **runtime_snapshot)
            _runtime_log("exit", **runtime_snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
