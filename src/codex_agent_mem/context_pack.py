from __future__ import annotations

from math import ceil
from typing import Any


def _compact_line(value: str, limit: int = 90) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def _approx_tokens(char_count: int) -> int:
    return max(1, ceil(char_count / 4))


def build_context_pack(
    *,
    project: dict[str, Any],
    decisions: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    source_turns: list[dict[str, Any]] | None = None,
    max_chars: int = 2200,
) -> dict[str, Any]:
    header = [
        "## Working Memory",
        "",
        f"Scope: `{project['project_key']}`",
        "",
    ]
    lines = list(header)
    source_chars = 0
    decision_lines: list[str] = []
    summary_lines: list[str] = []

    unique_decisions: set[str] = set()
    for item in decisions:
        decision_text = _compact_line(item.get("decision_text") or item.get("summary") or item.get("title") or "")
        if not decision_text:
            continue
        dedupe_key = decision_text.casefold()
        if dedupe_key in unique_decisions:
            continue
        unique_decisions.add(dedupe_key)
        candidate = f"- {decision_text}"
        if len(decision_lines) >= 2:
            break
        if len("\n".join(lines + ["### Stable decisions"] + decision_lines + [candidate])) > max_chars:
            break
        decision_lines.append(candidate)

    unique_summaries: set[str] = set()
    for item in summaries:
        summary_text = _compact_line(item.get("summary") or item.get("detail") or "")
        if not summary_text:
            continue
        dedupe_key = summary_text.casefold()
        if dedupe_key in unique_summaries:
            continue
        unique_summaries.add(dedupe_key)
        candidate = f"- {summary_text}"
        if len(summary_lines) >= 2:
            break
        if len(
            "\n".join(
                lines
                + ["### Stable decisions"]
                + (decision_lines or ["- No durable decisions extracted yet."])
                + [""]
                + ["### Recent continuity"]
                + summary_lines
                + [candidate]
            )
        ) > max_chars:
            break
        summary_lines.append(candidate)

    lines.append("### Stable decisions")
    lines.extend(decision_lines or ["- No durable decisions extracted yet."])
    lines.append("")
    lines.append("### Recent continuity")
    lines.extend(summary_lines or ["- No recent continuity summary extracted yet."])
    lines.append("")
    lines.append("### Resume")
    lines.append("- Start from the latest matching item above.")
    lines.append("- Use MCP only for older detail not already covered here.")

    text = "\n".join(lines).strip()
    pack_chars = len(text)
    for turn in source_turns or []:
        for message in turn.get("input_messages") or []:
            source_chars += len(message or "")
        source_chars += len(turn.get("assistant_message") or "")
    if source_chars <= 0:
        source_chars = pack_chars
    approx_source_tokens = _approx_tokens(source_chars or pack_chars)
    approx_pack_tokens = _approx_tokens(pack_chars)
    return {
        "text": text,
        "stats": {
            "source_char_count": source_chars or pack_chars,
            "pack_char_count": pack_chars,
            "approx_source_tokens": approx_source_tokens,
            "approx_pack_tokens": approx_pack_tokens,
            "compression_ratio": round(pack_chars / max(source_chars or pack_chars, 1), 3),
            "decision_count": len(decision_lines),
            "summary_count": len(summary_lines),
            "max_chars": max_chars,
        },
    }
