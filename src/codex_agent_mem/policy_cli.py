from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_agent_mem.config import AppConfig
from codex_agent_mem.db import CodexAgentMemStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage codex-agent-mem memory policies")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List project policies")
    list_cmd.add_argument("--project-key", required=True)

    validate_cmd = sub.add_parser("validate", help="Validate one policy rule")
    validate_cmd.add_argument("--policy-kind", required=True)
    validate_cmd.add_argument("--rule-json", required=True)

    add_cmd = sub.add_parser("add", help="Add one project policy")
    add_cmd.add_argument("--project-key", required=True)
    add_cmd.add_argument("--policy-kind", required=True)
    add_cmd.add_argument("--rule-json", required=True)

    remove_cmd = sub.add_parser("remove", help="Remove one project policy")
    remove_cmd.add_argument("--project-key", required=True)
    remove_cmd.add_argument("--policy-id", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = CodexAgentMemStore(args.db_path)

    if args.command == "list":
        result = store.list_policies(args.project_key)
    elif args.command == "validate":
        result = store.validate_policy(args.policy_kind, json.loads(args.rule_json))
    elif args.command == "add":
        result = store.add_policy(args.project_key, args.policy_kind, json.loads(args.rule_json))
    elif args.command == "remove":
        result = store.remove_policy(args.project_key, args.policy_id)
    else:
        raise ValueError(f"Unknown command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
