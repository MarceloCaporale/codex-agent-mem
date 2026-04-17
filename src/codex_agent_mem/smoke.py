from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_agent_mem.config import AppConfig
from codex_agent_mem.codex_notify import codex_notify_to_generic
from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event


def build_sample_payload(cwd: str) -> dict:
    return {
        "type": "agent-turn-complete",
        "thread-id": "smoke-thread",
        "turn-id": "smoke-turn",
        "cwd": cwd,
        "input-messages": ["Please summarize the auth direction"],
        "last-assistant-message": "Decision: keep sqlite for local persistence\nDone.",
        "timestamp": "2026-04-17T00:00:00Z",
    }


def run_smoke(db_path: Path, project_key: str) -> dict:
    store = CodexAgentMemStore(db_path)
    raw = build_sample_payload(cwd=str(Path.cwd()))
    generic_payload = codex_notify_to_generic(raw, project_key)
    result = store.ingest_event(raw, normalize_event(generic_payload))
    brief = store.project_brief(project_key)
    recent = store.recent_observations(project_key=project_key, limit=5)
    if not result["ok"]:
        raise RuntimeError("Smoke ingest failed")
    if not brief or not recent:
        raise RuntimeError("Smoke retrieval failed")
    return {
        "ingest": result,
        "brief": brief,
        "recent": recent,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a minimal end-to-end smoke test against codex_agent_mem")
    parser.add_argument("--db-path", type=Path, default=AppConfig().db_path)
    parser.add_argument("--project-key", default="codex-agent-mem-smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_smoke(db_path=args.db_path, project_key=args.project_key)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
