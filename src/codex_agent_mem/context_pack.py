from __future__ import annotations

from math import ceil
from typing import Any

PACK_BUDGETS: dict[str, dict[str, int]] = {
    "micro": {
        "max_chars": 1000,
        "decision_limit": 1,
        "request_limit": 1,
        "constraint_limit": 2,
        "dod_missing_limit": 2,
        "pending_limit": 3,
        "blocker_limit": 2,
        "completed_limit": 1,
        "summary_limit": 0,
        "guardrail_limit": 2,
    },
    "normal": {
        "max_chars": 2200,
        "decision_limit": 2,
        "request_limit": 1,
        "constraint_limit": 3,
        "dod_missing_limit": 3,
        "pending_limit": 4,
        "blocker_limit": 3,
        "completed_limit": 2,
        "summary_limit": 1,
        "guardrail_limit": 2,
    },
    "full": {
        "max_chars": 3600,
        "decision_limit": 4,
        "request_limit": 2,
        "constraint_limit": 4,
        "dod_missing_limit": 5,
        "pending_limit": 6,
        "blocker_limit": 4,
        "completed_limit": 3,
        "summary_limit": 2,
        "guardrail_limit": 3,
    },
}
AUTO_BUDGET_ORDER = ("micro", "normal", "full")


def _compact_line(value: str, limit: int = 90) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def _approx_tokens(char_count: int) -> int:
    return max(1, ceil(char_count / 4))


def resolve_pack_budget(budget: str = "normal", max_chars: int | None = None) -> dict[str, Any]:
    selected = dict(PACK_BUDGETS.get(budget, PACK_BUDGETS["normal"]))
    selected["budget"] = budget if budget in PACK_BUDGETS else "normal"
    if max_chars is not None:
        selected["max_chars"] = max_chars
    return selected


def choose_auto_budget(
    operational_state: dict[str, Any] | None = None,
    *,
    max_chars: int | None = None,
) -> tuple[str, str]:
    operational_state = operational_state or {}
    pending_count = len(operational_state.get("pending_items") or [])
    blocker_count = len(operational_state.get("blockers") or [])
    dod_missing_count = len(((operational_state.get("dod_missing") or {}).get("all_items") or []))
    constraint_count = len(operational_state.get("constraints") or [])
    summary_count = 1 if operational_state.get("user_requests") else 0

    required = {
        "pending_limit": pending_count,
        "blocker_limit": blocker_count,
        "dod_missing_limit": dod_missing_count,
        "constraint_limit": constraint_count,
        "summary_limit": summary_count,
    }
    for name in AUTO_BUDGET_ORDER:
        profile = resolve_pack_budget(name, max_chars=max_chars)
        if all(int(profile[key]) >= value for key, value in required.items()):
            return name, "fits_open_work_profile"
    return "full", "requires_full_profile"


def build_context_pack(
    *,
    project: dict[str, Any],
    decisions: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    operational_state: dict[str, Any] | None = None,
    source_turns: list[dict[str, Any]] | None = None,
    budget: str = "normal",
    max_chars: int | None = None,
    budget_reason: str | None = None,
) -> dict[str, Any]:
    operational_state = operational_state or {}
    profile = resolve_pack_budget(budget=budget, max_chars=max_chars)
    max_chars = int(profile["max_chars"])
    header = [
        "## Working Memory",
        "",
        f"Scope: `{project['project_key']}`",
        f"Budget: `{profile['budget']}`",
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
        if len(unique_decisions) >= int(profile["decision_limit"]):
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
        if len(unique_summaries) >= int(profile["summary_limit"]):
            break

    _add_section("Objective", objective_lines)
    if not objective_lines:
        _add_section(
            "Active User Scope",
            _bullets_from_items(operational_state.get("user_requests") or [], "summary")[: int(profile["request_limit"])],
        )
    _add_section("Stable decisions", unique_decisions, fallback="- No durable decisions extracted yet.")
    _add_section("Constraints", _bullets_from_items(operational_state.get("constraints") or [], "summary")[: int(profile["constraint_limit"])])
    _add_section(
        "Definition of Done gaps",
        _bullets_from_items(((operational_state.get("dod_missing") or {}).get("all_items") or []), "summary")[: int(profile["dod_missing_limit"])],
    )
    _add_section("Pending work", _bullets_from_items(operational_state.get("pending_items") or [], "summary")[: int(profile["pending_limit"])])
    _add_section("Blockers", _bullets_from_items(operational_state.get("blockers") or [], "summary")[: int(profile["blocker_limit"])])
    _add_section("Done recently", _bullets_from_items(operational_state.get("completed_items") or [], "summary")[: int(profile["completed_limit"])])
    if int(profile["summary_limit"]) > 0 and len("\n".join(lines).strip()) < (max_chars * 0.55):
        _add_section("Recent continuity", unique_summaries[:1], fallback="- No recent continuity summary extracted yet.")
    elif int(profile["summary_limit"]) > 0 and not unique_summaries:
        _add_section("Recent continuity", unique_summaries, fallback="- No recent continuity summary extracted yet.")
    _add_section(
        "Scope guard",
        [f"- {_compact_line(item, limit=96)}" for item in (operational_state.get("guardrails") or [])][: int(profile["guardrail_limit"])],
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
            "budget": profile["budget"],
            "budget_reason": budget_reason,
            "max_chars": max_chars,
            "section_counts": section_counts,
            "has_open_work": bool(operational_state.get("has_open_work")),
        },
        "operational_state": operational_state,
    }
