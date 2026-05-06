from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codex_agent_mem.config import AppConfig
from codex_agent_mem.mcp_stdio import MUTATING_TOOLS, PROFILE_TOOLS


def _tools_for_profile(profile: str, *, read_only: bool) -> tuple[str, ...]:
    try:
        tools = PROFILE_TOOLS[profile]
    except KeyError as exc:
        raise ValueError(f"Unknown MCP profile: {profile}") from exc
    if read_only:
        return tuple(tool for tool in tools if tool not in MUTATING_TOOLS)
    return tools


def build_codex_toml_snippet(
    *,
    python_exe: str,
    db_path: Path,
    server_name: str = "codex-agent-mem",
    project_from_cwd: bool = True,
    sync_project_doc: bool = False,
    idle_timeout_seconds: int = 300,
    mcp_profile: str = "full",
    mcp_read_only: bool = False,
    response_mode: str = "compact",
) -> str:
    lines = [
        "# Paste this into ~/.codex/config.toml",
        "notify = [",
        f"  '{python_exe}',",
        "  '-m',",
        "  'codex_agent_mem.codex_notify',",
    ]
    if sync_project_doc:
        lines.append("  '--sync-project-doc',")
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
            "  '--idle-timeout-seconds',",
            f"  '{idle_timeout_seconds}',",
            "  '--profile',",
            f"  '{mcp_profile}',",
            "  '--response-mode',",
            f"  '{response_mode}',",
        ]
    )
    if mcp_read_only:
        lines.append("  '--read-only',")
    lines.extend(
        [
            "  '--db-path',",
            f"  '{db_path}',",
            "]",
        ]
    )
    for tool_name in _tools_for_profile(mcp_profile, read_only=mcp_read_only):
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
    parser.add_argument("--sync-project-doc", action="store_true")
    parser.add_argument("--idle-timeout-seconds", type=int, default=300)
    parser.add_argument("--mcp-profile", choices=["minimal", "standard", "full"], default="full")
    parser.add_argument("--mcp-read-only", action="store_true")
    parser.add_argument("--response-mode", choices=["compact", "balanced", "verbose"], default="compact")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    snippet = build_codex_toml_snippet(
        python_exe=args.python_exe,
        db_path=args.db_path,
        server_name=args.server_name,
        project_from_cwd=not args.no_project_from_cwd,
        sync_project_doc=args.sync_project_doc,
        idle_timeout_seconds=args.idle_timeout_seconds,
        mcp_profile=args.mcp_profile,
        mcp_read_only=args.mcp_read_only,
        response_mode=args.response_mode,
    )
    print(snippet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
