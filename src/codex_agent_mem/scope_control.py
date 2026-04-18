from __future__ import annotations

from typing import Any

from codex_agent_mem.operational_state import normalize_state_text, state_text_matches


def _normalized_item(item: dict[str, Any]) -> str:
    return item.get("normalized_text") or normalize_state_text(
        item.get("summary") or item.get("detail") or item.get("title") or ""
    )


def _contains_match(item: dict[str, Any], items: list[dict[str, Any]]) -> bool:
    needle = _normalized_item(item)
    return any(state_text_matches(needle, _normalized_item(other)) for other in items)


def _added_items(current: list[dict[str, Any]], previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in current if not _contains_match(item, previous)]


def _removed_items(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in previous if not _contains_match(item, current)]


def build_scope_guard(
    operational_state: dict[str, Any],
    completion_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    completion_check = completion_check or {}
    objective = operational_state.get("objective")
    constraints = operational_state.get("constraints") or []
    pending_items = operational_state.get("pending_items") or []
    blockers = operational_state.get("blockers") or []
    dod_missing = ((operational_state.get("dod_missing") or {}).get("all_items") or [])
    guardrails = operational_state.get("guardrails") or []

    must_not_drop: list[str] = []
    if objective and objective.get("summary"):
        must_not_drop.append(objective["summary"])
    for group in (constraints, pending_items, blockers, dod_missing):
        for item in group:
            text = item.get("summary") or item.get("title") or ""
            if text and text not in must_not_drop:
                must_not_drop.append(text)

    conflict_flags: list[str] = []
    if completion_check.get("closure_mismatch"):
        conflict_flags.append("closure_mismatch")
    if completion_check.get("pending_count"):
        conflict_flags.append("pending_work_open")
    if completion_check.get("blocker_count"):
        conflict_flags.append("blockers_open")
    if completion_check.get("dod_missing_count"):
        conflict_flags.append("dod_incomplete")

    return {
        "objective": objective,
        "constraints": constraints,
        "pending_items": pending_items,
        "blockers": blockers,
        "dod_missing": dod_missing,
        "guardrails": guardrails,
        "must_not_drop": must_not_drop,
        "conflict_flags": conflict_flags,
        "has_open_work": bool(operational_state.get("has_open_work")),
        "completion_check": completion_check,
    }


def build_recent_changes(
    *,
    current_state: dict[str, Any],
    previous_state: dict[str, Any] | None,
    recent_decisions: list[dict[str, Any]],
    since: str | None,
    baseline_source: str,
) -> dict[str, Any]:
    previous_state = previous_state or {
        "constraints": [],
        "pending_items": [],
        "blockers": [],
        "dod_missing": {"all_items": []},
        "user_requests": [],
    }

    current_pending = current_state.get("pending_items") or []
    previous_pending = previous_state.get("pending_items") or []
    current_blockers = current_state.get("blockers") or []
    previous_blockers = previous_state.get("blockers") or []
    current_dod = ((current_state.get("dod_missing") or {}).get("all_items") or [])
    previous_dod = ((previous_state.get("dod_missing") or {}).get("all_items") or [])
    current_constraints = current_state.get("constraints") or []
    previous_constraints = previous_state.get("constraints") or []

    current_objective = current_state.get("objective")
    previous_objective = previous_state.get("objective")
    objective_changed = False
    if current_objective or previous_objective:
        objective_changed = not state_text_matches(
            normalize_state_text((current_objective or {}).get("summary") or ""),
            normalize_state_text((previous_objective or {}).get("summary") or ""),
        )

    latest_request = None
    user_requests = current_state.get("user_requests") or []
    if user_requests:
        latest_request = user_requests[0]

    new_pending = _added_items(current_pending, previous_pending)
    resolved_pending = _removed_items(previous_pending, current_pending)
    new_blockers = _added_items(current_blockers, previous_blockers)
    cleared_blockers = _removed_items(previous_blockers, current_blockers)
    new_dod_gaps = _added_items(current_dod, previous_dod)
    cleared_dod_gaps = _removed_items(previous_dod, current_dod)
    new_constraints = _added_items(current_constraints, previous_constraints)
    cleared_constraints = _removed_items(previous_constraints, current_constraints)

    has_changes = any(
        [
            objective_changed,
            new_pending,
            resolved_pending,
            new_blockers,
            cleared_blockers,
            new_dod_gaps,
            cleared_dod_gaps,
            new_constraints,
            cleared_constraints,
            recent_decisions,
        ]
    )

    return {
        "since": since,
        "baseline_source": baseline_source,
        "objective_changed": objective_changed,
        "latest_user_request": latest_request,
        "new_pending_items": new_pending,
        "resolved_pending_items": resolved_pending,
        "new_blockers": new_blockers,
        "cleared_blockers": cleared_blockers,
        "new_dod_gaps": new_dod_gaps,
        "cleared_dod_gaps": cleared_dod_gaps,
        "new_constraints": new_constraints,
        "cleared_constraints": cleared_constraints,
        "new_decisions": recent_decisions,
        "has_changes": has_changes,
    }
