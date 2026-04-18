from __future__ import annotations

import re
from typing import Any

STATE_TEXT_STOPWORDS = {"a", "an", "the", "is", "are", "still", "yet"}

STATEFUL_OBSERVATION_TYPES = {
    "objective",
    "user_request",
    "constraint",
    "project_dod",
    "mission_dod",
    "session_dod",
    "pending_item",
    "completed_item",
    "blocker",
    "completion_claim",
}


def normalize_state_text(value: str) -> str:
    compact = " ".join((value or "").split()).casefold()
    compact = re.sub(r"\bis still missing\b", " missing", compact)
    compact = re.sub(r"\bstill missing\b", " missing", compact)
    compact = re.sub(r"\bno\s+(.+?)\s+yet\b", r"\1 missing", compact)
    compact = re.sub(r"[^\w\s]", " ", compact)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact


def _dedupe_latest(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: list[str] = []
    for item in items:
        normalized = normalize_state_text(item.get("summary") or item.get("detail") or item.get("title") or "")
        if not normalized or any(_state_text_matches(normalized, existing) for existing in seen):
            continue
        seen.append(normalized)
        payload = dict(item)
        payload["normalized_text"] = normalized
        result.append(payload)
        if len(result) >= limit:
            break
    return result


def _state_token_set(value: str) -> set[str]:
    return {token for token in normalize_state_text(value).split() if token and token not in STATE_TEXT_STOPWORDS}


def _state_text_matches(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) >= 18 and left in right:
        return True
    if len(right) >= 18 and right in left:
        return True
    left_tokens = _state_token_set(left)
    right_tokens = _state_token_set(right)
    if left_tokens and right_tokens:
        if left_tokens == right_tokens:
            return True
        if left_tokens.issubset(right_tokens) or right_tokens.issubset(left_tokens):
            return True
    return False


def state_text_matches(left: str, right: str) -> bool:
    return _state_text_matches(left, right)


def _is_resolved(pending_key: str, completed_keys: set[str]) -> bool:
    for completed_key in completed_keys:
        if _state_text_matches(pending_key, completed_key):
            return True
    return False


def _unresolved_items(items: list[dict[str, Any]], completed_keys: set[str]) -> list[dict[str, Any]]:
    return [item for item in items if not _is_resolved(item["normalized_text"], completed_keys)]


def derive_operational_state(observations: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = {kind: [] for kind in STATEFUL_OBSERVATION_TYPES}
    for item in observations:
        obs_type = item.get("type")
        if obs_type in by_type:
            by_type[obs_type].append(item)

    objective_candidates = _dedupe_latest(by_type["objective"], limit=1)
    request_candidates = _dedupe_latest(by_type["user_request"], limit=4)
    constraints = _dedupe_latest(by_type["constraint"], limit=4)
    project_dod = _dedupe_latest(by_type["project_dod"], limit=6)
    mission_dod = _dedupe_latest(by_type["mission_dod"], limit=6)
    session_dod = _dedupe_latest(by_type["session_dod"], limit=6)
    pending_candidates = _dedupe_latest(by_type["pending_item"], limit=6)
    completed_items = _dedupe_latest(by_type["completed_item"], limit=6)
    blockers = _dedupe_latest(by_type["blocker"], limit=4)
    completion_claims = _dedupe_latest(by_type["completion_claim"], limit=3)

    completed_keys = {item["normalized_text"] for item in completed_items}
    pending_items = _unresolved_items(pending_candidates, completed_keys)
    project_dod_missing = _unresolved_items(project_dod, completed_keys)
    mission_dod_missing = _unresolved_items(mission_dod, completed_keys)
    session_dod_missing = _unresolved_items(session_dod, completed_keys)
    all_dod_missing = project_dod_missing + mission_dod_missing + session_dod_missing

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
    if all_dod_missing:
        guardrails.append("Do not declare completion while Definition of Done items are still missing.")
    if completion_claims and pending_items:
        guardrails.append("A recent completion claim conflicts with open pending work. Re-check scope before closing.")
    if completion_claims and all_dod_missing:
        guardrails.append("A recent completion claim conflicts with Definition of Done gaps. Re-check closure before closing.")

    return {
        "objective": objective,
        "user_requests": request_candidates,
        "constraints": constraints,
        "dod": {
            "project_items": project_dod,
            "mission_items": mission_dod,
            "session_items": session_dod,
            "all_items": project_dod + mission_dod + session_dod,
        },
        "dod_missing": {
            "project_items": project_dod_missing,
            "mission_items": mission_dod_missing,
            "session_items": session_dod_missing,
            "all_items": all_dod_missing,
        },
        "pending_items": pending_items,
        "completed_items": completed_items,
        "blockers": blockers,
        "completion_claims": completion_claims,
        "guardrails": guardrails,
        "has_open_work": bool(pending_items or blockers or all_dod_missing),
    }
