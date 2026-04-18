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
