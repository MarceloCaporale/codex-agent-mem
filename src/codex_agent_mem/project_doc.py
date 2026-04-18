from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from codex_agent_mem.db import CodexAgentMemStore

START_MARKER = "<!-- codex-agent-mem:generated-context:start -->"
END_MARKER = "<!-- codex-agent-mem:generated-context:end -->"


def choose_project_doc_path(cwd: Path) -> Path:
    override_path = cwd / "AGENTS.override.md"
    if override_path.exists():
        return override_path
    return cwd / "AGENTS.md"


def render_managed_block(context_pack: dict[str, Any]) -> str:
    stats = context_pack["stats"]
    return "\n".join(
        [
            START_MARKER,
            "## codex-agent-mem Generated Context",
            "",
            f"> Budget: `{stats.get('budget', 'normal')}`",
            f"> Approx pack size: ~{stats['approx_pack_tokens']} tokens from ~{stats['approx_source_tokens']} source tokens.",
            "> This block is generated after completed Codex turns to keep continuity compact across sessions.",
            "",
            context_pack["text"],
            END_MARKER,
        ]
    ).strip()


def upsert_managed_block(path: Path, block: str) -> str:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    else:
        existing = (
            "# AGENTS.md\n\n"
            "Add stable repo guidance above or below the codex-agent-mem managed block.\n\n"
        )

    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )
    if START_MARKER in existing and END_MARKER in existing:
        updated = pattern.sub(block, existing, count=1)
    else:
        updated = existing.rstrip() + "\n\n" + block + "\n"

    path.write_text(updated, encoding="utf-8")
    return updated


def sync_project_doc(
    *,
    store: CodexAgentMemStore,
    project_key: str,
    cwd: Path,
    budget: str = "auto",
    max_chars: int | None = None,
) -> dict[str, Any] | None:
    if not cwd.exists() or not cwd.is_dir():
        return None

    context_pack = store.context_pack(project_key=project_key, max_chars=max_chars, budget=budget)
    if context_pack is None:
        return None
    if context_pack["stats"]["approx_pack_tokens"] >= context_pack["stats"]["approx_source_tokens"]:
        result = {
            "path": None,
            "project_key": project_key,
            "skipped": True,
            "reason": "context_pack_not_smaller_than_source",
            "stats": context_pack["stats"],
            "text": context_pack["text"],
        }
        store.record_context_sync(
            project_key=project_key,
            target_path=None,
            skipped=True,
            reason=result["reason"],
            stats=context_pack["stats"],
        )
        return result
    target_path = choose_project_doc_path(cwd)
    upsert_managed_block(target_path, render_managed_block(context_pack))
    result = {
        "path": str(target_path),
        "project_key": project_key,
        "skipped": False,
        "stats": context_pack["stats"],
        "text": context_pack["text"],
    }
    store.record_context_sync(
        project_key=project_key,
        target_path=str(target_path),
        skipped=False,
        reason=None,
        stats=context_pack["stats"],
    )
    return result
