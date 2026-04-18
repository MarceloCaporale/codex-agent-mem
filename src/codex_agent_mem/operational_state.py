from __future__ import annotations

import re
from typing import Any

STATEFUL_OBSERVATION_TYPES = {
    "objective",
    "user_request",
    "constraint",
    "pending_item",
    "completed_item",
    "blocker",
    "completion_claim",
}


def normalize_state_text(value: str) -> str:
    compact = " ".join((value or "").split()).casefold()
    compact = re.sub(r"[^\w\s]", " ", compact)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact


def _dedupe_latest(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        normalized = normalize_state_text(item.get("summary") or item.get("detail") or item.get("title") or "")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        payload = dict(item)
        payload["normalized_text"] = normalized
        result.append(payload)
        if len(result) >= limit:
            break
    return result


def _is_resolved(pending_key: str, completed_keys: set[str]) -> bool:
    for completed_key in completed_keys:
        if pending_key == completed_key:
            return True
        if len(pending_key) >= 18 and pending_key in completed_key:
            return True
        if len(completed_key) >= 18 and completed_key in pending_key:
            return True
    return False


def derive_operational_state(observations: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = {kind: [] for kind in STATEFUL_OBSERVATION_TYPES}
    for item in observations:
        obs_type = item.get("type")
        if obs_type in by_type:
            by_type[obs_type].append(item)

    objective_candidates = _dedupe_latest(by_type["objective"], limit=1)
    request_candidates = _dedupe_latest(by_type["user_request"], limit=4)
    constraints = _dedupe_latest(by_type["constraint"], limit=4)
    pending_candidates = _dedupe_latest(by_type["pending_item"], limit=6)
    completed_items = _dedupe_latest(by_type["completed_item"], limit=6)
    blockers = _dedupe_latest(by_type["blocker"], limit=4)
    completion_claims = _dedupe_latest(by_type["completion_claim"], limit=3)

    completed_keys = {item["normalized_text"] for item in completed_items}
    pending_items = [
        item
        for item in pending_candidates
        if not _is_resolved(item["normalized_text"], completed_keys)
    ]

    objective = None
    if objective_candidates:
        objective = objective_candidates[0]
    elif request_candidates:
        objective = request_candidates[0]

    guardrails: list[str] = []
    if pending_items:
        guardrails.append("Do not declare completion while pending work remains.")
        guardrails.append("Before closing, confirm each pending item explicitly.")
    if request_candidates:
        guardrails.append("Keep the active user request in scope; do not silently narrow it.")
    if blockers:
        guardrails.append("If blockers remain, say blocked and list them instead of saying done.")
    if completion_claims and pending_items:
        guardrails.append("A recent completion claim conflicts with open pending work. Re-check scope before closing.")

    return {
        "objective": objective,
        "user_requests": request_candidates,
        "constraints": constraints,
        "pending_items": pending_items,
        "completed_items": completed_items,
        "blockers": blockers,
        "completion_claims": completion_claims,
        "guardrails": guardrails,
        "has_open_work": bool(pending_items or blockers),
    }
