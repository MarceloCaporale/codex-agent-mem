from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_agent_mem.config import AppConfig
from codex_agent_mem.db import CodexAgentMemStore


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage codex-agent-mem snapshots")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a snapshot")
    create.add_argument("--project-key", required=True)
    create.add_argument("--label", required=True)

    list_cmd = subparsers.add_parser("list", help="List snapshots")
    list_cmd.add_argument("--project-key", required=True)
    list_cmd.add_argument("--limit", type=int, default=20)

    restore = subparsers.add_parser("restore", help="Restore a snapshot into AGENTS.md when possible")
    restore.add_argument("--project-key", required=True)
    restore.add_argument("--snapshot-id", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    store = CodexAgentMemStore(args.db_path)

    if args.command == "create":
        result = store.snapshot_create(args.project_key, args.label)
    elif args.command == "list":
        result = store.list_snapshots(args.project_key, limit=args.limit)
    else:
        result = store.snapshot_restore(args.project_key, args.snapshot_id)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
