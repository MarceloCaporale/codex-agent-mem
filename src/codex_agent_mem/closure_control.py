from __future__ import annotations

from typing import Any


def build_completion_check(operational_state: dict[str, Any] | None) -> dict[str, Any]:
    state = operational_state or {}
    pending_items = state.get("pending_items") or []
    blockers = state.get("blockers") or []
    completed_items = state.get("completed_items") or []
    completion_claims = state.get("completion_claims") or []
    dod_missing = ((state.get("dod_missing") or {}).get("all_items")) or []
    reasons: list[str] = []

    pending_count = len(pending_items)
    blocker_count = len(blockers)
    dod_missing_count = len(dod_missing)
    evidence_count = len(completed_items)
    completion_claim_count = len(completion_claims)

    if pending_count:
        reasons.append("pending_items_open")
    if blocker_count:
        reasons.append("blockers_open")
    if dod_missing_count:
        reasons.append("dod_incomplete")
    if evidence_count == 0:
        reasons.append("missing_evidence")

    done = not reasons
    return {
        "done": done,
        "primary_reason": "ready_to_close" if done else reasons[0],
        "reasons": reasons,
        "pending_count": pending_count,
        "blocker_count": blocker_count,
        "dod_missing_count": dod_missing_count,
        "evidence_count": evidence_count,
        "completion_claim_count": completion_claim_count,
        "has_open_work": bool(pending_count or blocker_count or dod_missing_count),
        "closure_mismatch": bool(completion_claim_count and not done),
        "pending_items": pending_items,
        "blockers": blockers,
        "dod_missing": dod_missing,
        "evidence_items": completed_items,
        "completion_claims": completion_claims,
    }


def build_open_work_report(operational_state: dict[str, Any] | None) -> dict[str, Any]:
    state = operational_state or {}
    completion_check = build_completion_check(state)
    return {
        "objective": state.get("objective"),
        "constraints": state.get("constraints") or [],
        "pending_items": state.get("pending_items") or [],
        "blockers": state.get("blockers") or [],
        "dod": state.get("dod") or {},
        "dod_missing": (state.get("dod_missing") or {}).get("all_items") or [],
        "guardrails": state.get("guardrails") or [],
        "has_open_work": completion_check["has_open_work"],
        "completion_check": completion_check,
    }
