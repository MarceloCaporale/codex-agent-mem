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
    operational_state: dict[str, Any] | None = None,
    source_turns: list[dict[str, Any]] | None = None,
    max_chars: int = 2200,
) -> dict[str, Any]:
    operational_state = operational_state or {}
    header = [
        "## Working Memory",
        "",
        f"Scope: `{project['project_key']}`",
        "",
    ]
    lines = list(header)
    source_chars = 0
    section_counts: dict[str, int] = {}

    def _add_section(title: str, candidates: list[str], fallback: str | None = None) -> None:
        section_lines = [f"### {title}"]
        added = 0
        for candidate in candidates:
            if not candidate:
                continue
            test_lines = lines + section_lines + [candidate, ""]
            if len("\n".join(test_lines).strip()) > max_chars:
                break
            section_lines.append(candidate)
            added += 1
        if added == 0 and fallback:
            fallback_lines = lines + [f"### {title}", fallback, ""]
            if len("\n".join(fallback_lines).strip()) <= max_chars:
                section_lines.append(fallback)
        if len(section_lines) > 1:
            section_lines.append("")
            lines.extend(section_lines)
            section_counts[title] = len(section_lines) - 2

    def _bullets_from_items(items: list[dict[str, Any]], field: str) -> list[str]:
        bullets: list[str] = []
        for item in items:
            text = _compact_line(item.get(field) or item.get("summary") or item.get("title") or "")
            if text:
                bullets.append(f"- {text}")
        return bullets

    objective = operational_state.get("objective")
    objective_lines = []
    if objective:
        objective_lines = [f"- {_compact_line(objective.get('summary') or objective.get('title') or '')}"]

    unique_decisions: list[str] = []
    seen_decisions: set[str] = set()
    for item in decisions:
        decision_text = _compact_line(item.get("decision_text") or item.get("summary") or item.get("title") or "")
        if not decision_text:
            continue
        dedupe_key = decision_text.casefold()
        if dedupe_key in seen_decisions:
            continue
        seen_decisions.add(dedupe_key)
        unique_decisions.append(f"- {decision_text}")
        if len(unique_decisions) >= 2:
            break

    unique_summaries: list[str] = []
    seen_summaries: set[str] = set()
    for item in summaries:
        summary_text = _compact_line(item.get("summary") or item.get("detail") or "")
        if not summary_text:
            continue
        dedupe_key = summary_text.casefold()
        if dedupe_key in seen_summaries:
            continue
        seen_summaries.add(dedupe_key)
        unique_summaries.append(f"- {summary_text}")
        if len(unique_summaries) >= 2:
            break

    _add_section("Objective", objective_lines)
    if not objective_lines:
        _add_section(
            "Active User Scope",
            _bullets_from_items(operational_state.get("user_requests") or [], "summary")[:1],
        )
    _add_section("Stable decisions", unique_decisions, fallback="- No durable decisions extracted yet.")
    _add_section("Constraints", _bullets_from_items(operational_state.get("constraints") or [], "summary")[:3])
    _add_section("Pending work", _bullets_from_items(operational_state.get("pending_items") or [], "summary")[:4])
    _add_section("Blockers", _bullets_from_items(operational_state.get("blockers") or [], "summary")[:3])
    _add_section("Done recently", _bullets_from_items(operational_state.get("completed_items") or [], "summary")[:2])
    if len("\n".join(lines).strip()) < (max_chars * 0.55):
        _add_section("Recent continuity", unique_summaries[:1], fallback="- No recent continuity summary extracted yet.")
    elif not unique_summaries:
        _add_section("Recent continuity", unique_summaries, fallback="- No recent continuity summary extracted yet.")
    _add_section(
        "Scope guard",
        [f"- {_compact_line(item, limit=96)}" for item in (operational_state.get("guardrails") or [])][:2],
    )
    _add_section(
        "Resume",
        [
            "- Start from the latest matching item above.",
            "- Use MCP only for older detail not already covered here.",
        ],
    )

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
            "decision_count": len(unique_decisions),
            "summary_count": len(unique_summaries),
            "max_chars": max_chars,
            "section_counts": section_counts,
            "has_open_work": bool(operational_state.get("has_open_work")),
        },
        "operational_state": operational_state,
    }
