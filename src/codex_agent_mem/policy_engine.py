from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

POLICY_KINDS = {
    "never_archive",
    "always_keep_priority",
    "auto_archive_after",
    "tag_as",
    "exclude_from_pack",
}
INHERITANCE_MODES = {
    "rules_only",
    "stable_decisions",
    "marked_inheritable",
    "combined",
}
DEFAULT_POLICY_SCOPES: dict[str, list[str]] = {
    "never_archive": ["pack", "retrieval", "repair"],
    "always_keep_priority": ["pack", "retrieval"],
    "auto_archive_after": ["pack", "retrieval"],
    "tag_as": [],
    "exclude_from_pack": ["pack"],
}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_str_list(value: Any) -> list[str]:
    result: list[str] = []
    for item in _as_list(value):
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text:
            result.append(text)
    return result


def _clean_int_list(value: Any) -> list[int]:
    result: list[int] = []
    for item in _as_list(value):
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip().casefold()


def _item_text(item: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            str(item.get("title") or "").strip(),
            str(item.get("summary") or "").strip(),
            str(item.get("detail") or "").strip(),
            str(item.get("decision_text") or "").strip(),
        ]
        if part
    ).casefold()


def _item_key(item: dict[str, Any]) -> str:
    memory_kind = str(item.get("memory_kind") or "observation")
    item_id = item.get("id")
    return f"{memory_kind}:{item_id}"


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_policy_definition(policy_kind: str, rule: dict[str, Any] | None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    normalized_rule: dict[str, Any] = {}
    if policy_kind not in POLICY_KINDS:
        return {
            "valid": False,
            "errors": [f"Unknown policy_kind: {policy_kind}"],
            "warnings": [],
            "normalized_rule": {},
        }

    raw_rule = rule or {}
    selector = raw_rule.get("selector") or {}
    normalized_selector = {
        "types": _clean_str_list(selector.get("types")),
        "statuses": _clean_str_list(selector.get("statuses")),
        "ids": _clean_int_list(selector.get("ids")),
        "text_contains": [item.casefold() for item in _clean_str_list(selector.get("text_contains"))],
        "tags": [item.casefold() for item in _clean_str_list(selector.get("tags"))],
    }
    if policy_kind != "tag_as" and not any(normalized_selector.values()):
        errors.append("selector must include at least one filter")
    if policy_kind == "tag_as" and normalized_selector["tags"]:
        warnings.append("selector.tags on tag_as can create confusing self-referential matches")
    normalized_rule["selector"] = normalized_selector
    normalized_rule["apply_to"] = _clean_str_list(raw_rule.get("apply_to")) or list(DEFAULT_POLICY_SCOPES[policy_kind])

    if policy_kind == "auto_archive_after":
        try:
            days = int(raw_rule.get("days"))
            if days <= 0:
                raise ValueError
            normalized_rule["days"] = days
        except (TypeError, ValueError):
            errors.append("auto_archive_after requires a positive integer days value")
    elif policy_kind == "tag_as":
        tags = [item.casefold() for item in _clean_str_list(raw_rule.get("tags"))]
        single_tag = str(raw_rule.get("tag") or "").strip().casefold()
        if single_tag:
            tags.append(single_tag)
        tags = sorted(set(item for item in tags if item))
        if not tags:
            errors.append("tag_as requires tag or tags")
        normalized_rule["tags"] = tags

    note = str(raw_rule.get("note") or "").strip()
    if note:
        normalized_rule["note"] = note

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "normalized_rule": normalized_rule,
    }


def validate_inheritance_definition(mode: str, selector: dict[str, Any] | None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    normalized_selector = selector or {}
    if mode not in INHERITANCE_MODES:
        errors.append(f"Unknown inheritance mode: {mode}")
    normalized = {
        "types": _clean_str_list(normalized_selector.get("types")),
        "tags": [item.casefold() for item in _clean_str_list(normalized_selector.get("tags"))],
        "text_contains": [item.casefold() for item in _clean_str_list(normalized_selector.get("text_contains"))],
        "limit": int(normalized_selector.get("limit") or 8),
    }
    if mode == "marked_inheritable" and not normalized["tags"]:
        normalized["tags"] = ["inheritable"]
    if normalized["limit"] <= 0:
        errors.append("selector.limit must be a positive integer")
    if mode == "rules_only" and any(
        normalized[key] for key in ("types", "tags", "text_contains")
    ):
        warnings.append("rules_only ignores selector item filters")
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "normalized_selector": normalized,
    }


def selector_matches(
    item: dict[str, Any],
    selector: dict[str, Any] | None,
    *,
    tags: set[str] | None = None,
) -> bool:
    selector = selector or {}
    types = set(selector.get("types") or [])
    if types and str(item.get("type") or "") not in types:
        return False
    statuses = set(selector.get("statuses") or [])
    if statuses and str(item.get("status") or "") not in statuses:
        return False
    ids = set(int(v) for v in selector.get("ids") or [])
    item_id = item.get("id")
    if ids and item_id not in ids:
        return False
    haystack = _item_text(item)
    for needle in selector.get("text_contains") or []:
        if needle not in haystack:
            return False
    required_tags = set(selector.get("tags") or [])
    if required_tags and not (required_tags & (tags or set())):
        return False
    return True


def apply_tag_policies(items: list[dict[str, Any]], policies: list[dict[str, Any]]) -> dict[str, set[str]]:
    tag_map: dict[str, set[str]] = {_item_key(item): set(item.get("effective_tags") or []) for item in items}
    for policy in policies:
        if policy.get("policy_kind") != "tag_as" or not policy.get("enabled", True):
            continue
        rule = policy.get("rule") or {}
        for item in items:
            key = _item_key(item)
            if selector_matches(item, rule.get("selector"), tags=tag_map.get(key)):
                tag_map.setdefault(key, set()).update(rule.get("tags") or [])
    return tag_map


def _item_is_stale(item: dict[str, Any], *, days: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    updated_at = _parse_iso(item.get("updated_at"))
    if updated_at is None:
        return False
    return updated_at <= (now - timedelta(days=days))


def evaluate_policy_effects(
    items: list[dict[str, Any]],
    policies: list[dict[str, Any]],
    approved_repairs: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    tag_map = apply_tag_policies(items, policies)
    explicit_pack_excluded: set[str] = set()
    archive_excluded: set[str] = set()
    keep_priority: set[str] = set()
    never_archive: set[str] = set()
    matches: list[dict[str, Any]] = []

    for policy in policies:
        if not policy.get("enabled", True):
            continue
        kind = str(policy.get("policy_kind"))
        rule = policy.get("rule") or {}
        matched_keys: list[str] = []
        for item in items:
            key = _item_key(item)
            tags = tag_map.get(key) or set()
            if not selector_matches(item, rule.get("selector"), tags=tags):
                continue
            matched_keys.append(key)
            if kind == "never_archive":
                never_archive.add(key)
            elif kind == "always_keep_priority":
                keep_priority.add(key)
            elif kind == "exclude_from_pack":
                explicit_pack_excluded.add(key)
            elif kind == "auto_archive_after":
                if _item_is_stale(item, days=int(rule.get("days") or 0), now=now):
                    archive_excluded.add(key)
        matches.append(
            {
                "policy_id": policy.get("id"),
                "policy_kind": kind,
                "matched_count": len(matched_keys),
                "matched_keys": matched_keys,
            }
        )

    for repair in approved_repairs or []:
        after_ref = repair.get("after_ref") or {}
        for observation_id in after_ref.get("exclude_observation_ids") or []:
            archive_excluded.add(f"observation:{observation_id}")

    retrieval_excluded = archive_excluded - never_archive
    pack_excluded = explicit_pack_excluded | retrieval_excluded
    keep_priority -= pack_excluded
    return {
        "tag_map": {key: sorted(value) for key, value in tag_map.items()},
        "pack_excluded_keys": sorted(pack_excluded),
        "retrieval_excluded_keys": sorted(retrieval_excluded),
        "keep_priority_keys": sorted(keep_priority),
        "never_archive_keys": sorted(never_archive),
        "matches": matches,
    }


def filter_items_by_policy(
    items: list[dict[str, Any]],
    *,
    excluded_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded_keys = excluded_keys or set()
    return [item for item in items if _item_key(item) not in excluded_keys]


def sort_items_for_priority(
    items: list[dict[str, Any]],
    *,
    priority_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    priority_keys = priority_keys or set()
    return sorted(
        items,
        key=lambda item: (
            0 if _item_key(item) in priority_keys else 1,
            str(item.get("updated_at") or ""),
            str(item.get("id") or ""),
        ),
        reverse=False,
    )

