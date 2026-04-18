from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codex_agent_mem.config import AppConfig


READ_ONLY_MCP_TOOLS = (
    "mem_search",
    "mem_get",
    "mem_recent",
    "mem_project_brief",
    "mem_open_work",
    "mem_completion_check",
    "mem_recent_changes",
    "mem_scope_guard",
    "mem_context_pack",
)


def build_codex_toml_snippet(
    *,
    python_exe: str,
    db_path: Path,
    server_name: str = "codex-agent-mem",
    project_from_cwd: bool = True,
) -> str:
    lines = [
        "# Paste this into ~/.codex/config.toml",
        "notify = [",
        f"  '{python_exe}',",
        "  '-m',",
        "  'codex_agent_mem.codex_notify',",
        "  '--sync-project-doc',",
    ]
    if project_from_cwd:
        lines.append("  '--project-from-cwd',")
    lines.extend(
        [
            "  '--db-path',",
            f"  '{db_path}',",
            "]",
            "",
            f'[mcp_servers."{server_name}"]',
            f"command = '{python_exe}'",
            "args = [",
            "  '-m',",
            "  'codex_agent_mem.mcp_stdio',",
            "  '--db-path',",
            f"  '{db_path}',",
            "]",
        ]
    )
    for tool_name in READ_ONLY_MCP_TOOLS:
        lines.extend(
            [
                "",
                f'[mcp_servers."{server_name}".tools.{tool_name}]',
                'approval_mode = "approve"',
            ]
        )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a ready-to-paste Codex config snippet for codex-agent-mem")
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    parser.add_argument("--server-name", default="codex-agent-mem")
    parser.add_argument("--no-project-from-cwd", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    snippet = build_codex_toml_snippet(
        python_exe=args.python_exe,
        db_path=args.db_path,
        server_name=args.server_name,
        project_from_cwd=not args.no_project_from_cwd,
    )
    print(snippet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
