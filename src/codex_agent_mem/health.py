from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from codex_agent_mem.operational_state import normalize_state_text, state_text_matches


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_items(items: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    for item in items:
        normalized = normalize_state_text(item.get("summary") or item.get("detail") or item.get("title") or "")
        if normalized:
            result.append((normalized, item))
    return result


def _find_duplicates(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in observations:
        normalized = normalize_state_text(item.get("summary") or item.get("detail") or item.get("title") or "")
        if not normalized:
            continue
        key = (str(item.get("type") or "unknown"), normalized)
        buckets.setdefault(key, []).append(item)

    duplicates: list[dict[str, Any]] = []
    for (item_type, normalized), items in buckets.items():
        if len(items) <= 1:
            continue
        duplicates.append(
            {
                "type": item_type,
                "normalized_text": normalized,
                "count": len(items),
                "observation_ids": [int(item["id"]) for item in items if item.get("id") is not None],
                "latest_summary": items[0].get("summary") or items[0].get("title") or "",
            }
        )
    return duplicates


def _find_contradictions(
    pending_items: list[dict[str, Any]],
    completed_items: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    completion_check: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    contradictions: list[dict[str, Any]] = []
    pending_norm = _normalized_items(pending_items)
    completed_norm = _normalized_items(completed_items)
    blocker_norm = _normalized_items(blockers)

    for pending_key, pending_item in pending_norm:
        for completed_key, completed_item in completed_norm:
            if state_text_matches(pending_key, completed_key):
                contradictions.append(
                    {
                        "kind": "pending_vs_completed",
                        "left": pending_item.get("summary") or pending_item.get("title") or "",
                        "right": completed_item.get("summary") or completed_item.get("title") or "",
                    }
                )
                break

    for blocker_key, blocker_item in blocker_norm:
        for completed_key, completed_item in completed_norm:
            if state_text_matches(blocker_key, completed_key):
                contradictions.append(
                    {
                        "kind": "blocker_vs_completed",
                        "left": blocker_item.get("summary") or blocker_item.get("title") or "",
                        "right": completed_item.get("summary") or completed_item.get("title") or "",
                    }
                )
                break

    if completion_check and completion_check.get("closure_mismatch"):
        contradictions.append(
            {
                "kind": "closure_mismatch",
                "left": "completion_claim",
                "right": ",".join(completion_check.get("reasons") or []),
            }
        )
    return contradictions


def _find_stale_items(
    state: dict[str, Any],
    *,
    stale_after_days: int = 30,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or _now_utc()
    cutoff = now - timedelta(days=stale_after_days)
    stale_items: list[dict[str, Any]] = []
    candidates = [
        ("pending_item", state.get("pending_items") or []),
        ("blocker", state.get("blockers") or []),
        ("constraint", state.get("constraints") or []),
        ("dod_missing", ((state.get("dod_missing") or {}).get("all_items") or [])),
    ]
    for kind, items in candidates:
        for item in items:
            updated_at = _parse_iso(item.get("updated_at"))
            if updated_at is None or updated_at >= cutoff:
                continue
            stale_items.append(
                {
                    "kind": kind,
                    "summary": item.get("summary") or item.get("title") or "",
                    "updated_at": item.get("updated_at"),
                }
            )
    return stale_items


def build_health_report(
    *,
    project_key: str,
    operational_state: dict[str, Any],
    operational_observations: list[dict[str, Any]],
    completion_check: dict[str, Any],
    stale_after_days: int = 30,
) -> dict[str, Any]:
    duplicates = _find_duplicates(operational_observations)
    contradictions = _find_contradictions(
        pending_items=operational_state.get("pending_items") or [],
        completed_items=operational_state.get("completed_items") or [],
        blockers=operational_state.get("blockers") or [],
        completion_check=completion_check,
    )
    stale_items = _find_stale_items(
        operational_state,
        stale_after_days=stale_after_days,
    )

    dod_total = len(((operational_state.get("dod") or {}).get("all_items") or []))
    dod_missing = len(((operational_state.get("dod_missing") or {}).get("all_items") or []))
    dod_coverage_ratio = 1.0 if dod_total == 0 else round(max(dod_total - dod_missing, 0) / dod_total, 3)
    open_work_count = (
        len(operational_state.get("pending_items") or [])
        + len(operational_state.get("blockers") or [])
        + dod_missing
    )

    score = 100
    score -= min(sum(item["count"] - 1 for item in duplicates) * 4, 20)
    score -= min(len(contradictions) * 15, 45)
    score -= min(len(stale_items) * 3, 15)
    score -= min(dod_missing * 8, 24)
    score = max(0, min(100, score))

    suggestions: list[str] = []
    if duplicates:
        suggestions.append("dedupe_stateful_items")
    if contradictions:
        suggestions.append("review_conflicting_open_and_completed_items")
    if stale_items:
        suggestions.append("review_stale_open_items")
    if dod_missing:
        suggestions.append("close_definition_of_done_gaps")

    return {
        "project_key": project_key,
        "score": score,
        "duplicate_count": sum(item["count"] - 1 for item in duplicates),
        "contradiction_count": len(contradictions),
        "stale_item_count": len(stale_items),
        "dod_total_count": dod_total,
        "dod_missing_count": dod_missing,
        "dod_coverage_ratio": dod_coverage_ratio,
        "open_work_count": open_work_count,
        "closure_mismatch": bool(completion_check.get("closure_mismatch")),
        "duplicates": duplicates,
        "contradictions": contradictions,
        "stale_items": stale_items,
        "suggestions": suggestions,
        "generated_at": _now_utc().isoformat(),
    }
