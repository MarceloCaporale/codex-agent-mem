from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_agent_mem.config import AppConfig
from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.project_doc import sync_project_doc


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the generated AGENTS.md working-memory block for one project")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    parser.add_argument("--project-key", required=True)
    parser.add_argument("--cwd", type=Path, required=True, help="Directory whose AGENTS.md or AGENTS.override.md should be updated")
    parser.add_argument("--max-chars", type=int, default=2200)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    store = CodexAgentMemStore(args.db_path)
    result = sync_project_doc(
        store=store,
        project_key=args.project_key,
        cwd=args.cwd,
        max_chars=args.max_chars,
    )
    if result is None:
        raise SystemExit("Could not build project context")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
