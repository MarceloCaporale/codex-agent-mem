from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from codex_agent_mem import __version__
from codex_agent_mem.config import AppConfig
from codex_agent_mem.db import CodexAgentMemStore


class CodexAgentMemMCPServer:
    def __init__(self, store: CodexAgentMemStore):
        self.store = store
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

        if method in {"initialized", "notifications/initialized"}:
            return None
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the codex-agent-mem MCP stdio server")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    args = parser.parse_args(argv)
    _configure_stdio()
    server = CodexAgentMemMCPServer(CodexAgentMemStore(args.db_path))
    for line in sys.stdin:
        line = line.strip()
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
