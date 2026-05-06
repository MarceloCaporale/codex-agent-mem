from __future__ import annotations

import hashlib
import re
from typing import Any

INTERNAL_PROMPT_PATTERNS = (
    "generate a concise ui title",
    "generate a clear, informative task title",
    "generate a short title",
    "the tasks typically have to do with coding-related tasks",
    "fill the structured title field",
)

PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/][^\n`\"']+|/[A-Za-z0-9_.\-/]+)")
REPO_LIKE_RE = re.compile(r"\b[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+\b")
VOLATILE_ID_RE = re.compile(r"\b(?:turn|session|project|observation)_?id\s*[:=]\s*[A-Za-z0-9_.:-]+\b", re.I)

BROAD_SCOPE_NAMES = {
    "lab",
    "src",
    "docs",
    "tests",
    "scripts",
    "workspace",
}

PROTECTED_OPERATIONAL_TYPES = {
    "blocker",
    "completion_claim",
    "constraint",
    "mission_dod",
    "objective",
    "pending_item",
    "project_dod",
    "session_dod",
}


def _compact(value: str, *, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    if limit is not None and len(text) > limit:
        return f"{text[: limit - 3].rstrip()}..."
    return text


def is_internal_prompt_noise(text: str) -> bool:
    normalized = _compact(text).casefold()
    return any(pattern in normalized for pattern in INTERNAL_PROMPT_PATTERNS)


def extract_embedded_user_prompt(text: str) -> str:
    match = re.search(r"user prompt:\s*(.+)\Z", text or "", flags=re.I | re.S)
    if not match:
        return ""
    return _compact(match.group(1), limit=300)


def first_operational_input(messages: list[Any]) -> dict[str, Any]:
    suppressed = False
    for message in messages:
        text = _compact(str(message or ""))
        if not text:
            continue
        embedded = extract_embedded_user_prompt(text)
        if embedded:
            return {
                "text": embedded,
                "internal_prompt_suppressed": True,
                "source": "embedded_user_prompt",
            }
        if is_internal_prompt_noise(text):
            suppressed = True
            continue
        return {
            "text": text,
            "internal_prompt_suppressed": suppressed,
            "source": "first_input",
        }
    return {"text": "", "internal_prompt_suppressed": suppressed, "source": "fallback"}


def normalize_memory_text(text: str) -> str:
    normalized = str(text or "").casefold().replace("\\", "/")
    normalized = VOLATILE_ID_RE.sub("", normalized)
    normalized = re.sub(r"\b\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:z|[+-]\d{2}:\d{2})?\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def item_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "")
        for field in ("summary", "detail", "title", "decision_text", "text")
        if item.get(field)
    )


def memory_fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_memory_text(text).encode("utf-8")).hexdigest()


def retrieval_fingerprint(item: dict[str, Any]) -> str:
    kind = str(item.get("type") or item.get("memory_kind") or "")
    status = str(item.get("status") or "")
    return memory_fingerprint("\0".join([kind, status, item_text(item)]))


def dedupe_retrieval_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    output: list[dict[str, Any]] = []
    duplicate_total = 0
    for item in items:
        text = item_text(item)
        if not text:
            output.append(dict(item, dedupe_applied=False, duplicate_count=1, duplicate_session_ids=[]))
            continue
        fp = retrieval_fingerprint(item)
        existing = seen.get(fp)
        if existing is not None:
            duplicate_total += 1
            existing["duplicate_count"] = int(existing.get("duplicate_count") or 1) + 1
            session_ids = set(existing.get("duplicate_session_ids") or [])
            if item.get("session_id") is not None:
                session_ids.add(int(item["session_id"]))
            existing["duplicate_session_ids"] = sorted(session_ids)
            external_ids = set(existing.get("duplicate_external_session_ids") or [])
            if item.get("external_session_id"):
                external_ids.add(str(item["external_session_id"]))
            if existing.get("external_session_id"):
                external_ids.add(str(existing["external_session_id"]))
            existing["duplicate_external_session_ids"] = sorted(external_ids)
            _merge_latest_timestamp(existing, item, target_key="duplicate_latest_updated_at", source_key="updated_at")
            _merge_latest_timestamp(
                existing,
                item,
                target_key="duplicate_latest_captured_turn_at",
                source_key="last_captured_turn_at",
            )
            existing["dedupe_applied"] = True
            continue
        enriched = dict(item)
        enriched["memory_fingerprint"] = fp
        enriched["dedupe_applied"] = False
        enriched["duplicate_count"] = 1
        enriched["duplicate_session_ids"] = [int(item["session_id"])] if item.get("session_id") is not None else []
        enriched["duplicate_external_session_ids"] = (
            [str(item["external_session_id"])] if item.get("external_session_id") else []
        )
        enriched["duplicate_latest_updated_at"] = item.get("updated_at")
        enriched["duplicate_latest_captured_turn_at"] = item.get("last_captured_turn_at")
        seen[fp] = enriched
        output.append(enriched)
    return output, {
        "dedupe_applied": duplicate_total > 0,
        "duplicates_collapsed": duplicate_total,
        "unique_count": len(output),
    }


def _timestamp_sort_key(value: Any) -> str:
    return str(value or "")


def _merge_latest_timestamp(
    target: dict[str, Any],
    item: dict[str, Any],
    *,
    target_key: str,
    source_key: str,
) -> None:
    current = target.get(target_key)
    candidate = item.get(source_key)
    if candidate and _timestamp_sort_key(candidate) > _timestamp_sort_key(current):
        target[target_key] = candidate


def _protected_item(item: dict[str, Any]) -> bool:
    return str(item.get("type") or item.get("memory_kind") or "").casefold() in PROTECTED_OPERATIONAL_TYPES


def cap_items_per_session(
    items: list[dict[str, Any]],
    *,
    max_items_per_session: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[int | None, list[tuple[int, dict[str, Any]]]] = {}
    original_counts: dict[int | None, int] = {}
    for index, item in enumerate(items):
        raw_session_id = item.get("session_id")
        session_id = int(raw_session_id) if raw_session_id is not None else None
        original_counts[session_id] = original_counts.get(session_id, 0) + 1
        grouped.setdefault(session_id, []).append((index, item))

    selected_indexes: set[int] = set()
    protected_retained = 0
    for session_id, session_items in grouped.items():
        if session_id is None:
            selected_indexes.update(index for index, _item in session_items)
            continue
        ranked = sorted(
            session_items,
            key=lambda pair: (
                0 if _protected_item(pair[1]) else 1,
                pair[0],
            ),
        )
        for index, item in ranked[:max_items_per_session]:
            selected_indexes.add(index)
            if _protected_item(item):
                protected_retained += 1

    output = [item for index, item in enumerate(items) if index in selected_indexes]
    counts: dict[int | None, int] = {}
    for item in output:
        raw_session_id = item.get("session_id")
        session_id = int(raw_session_id) if raw_session_id is not None else None
        counts[session_id] = counts.get(session_id, 0) + 1
    capped = [
        {
            "session_id": session_id,
            "original_item_count": original_count,
            "used_item_count": counts.get(session_id, 0),
        }
        for session_id, original_count in sorted(
            original_counts.items(),
            key=lambda pair: (-pair[1], -1 if pair[0] is None else int(pair[0])),
        )
        if session_id is not None and counts.get(session_id, 0) < original_count
    ]
    return output, {
        "dominance_guard_applied": bool(capped),
        "max_items_per_session": max_items_per_session,
        "protected_types": sorted(PROTECTED_OPERATIONAL_TYPES),
        "protected_items_retained": protected_retained,
        "sessions_capped": capped,
    }


def session_matches_query(session: dict[str, Any], query: str | None = None, sub_scope_hint: str | None = None) -> bool:
    terms = [item.casefold() for item in (query, sub_scope_hint) if item and str(item).strip()]
    if not terms:
        return True
    haystack = " ".join(
        str(value or "")
        for value in (
            session.get("display_label"),
            session.get("first_operational_input_preview"),
            session.get("first_input_preview"),
            session.get("external_session_id"),
            session.get("cwd"),
            session.get("inferred_sub_scope"),
            " ".join(str(item) for item in (session.get("sub_scope_candidates") or [])),
        )
    ).casefold()
    return all(term in haystack for term in terms)


def is_broad_scope_name(value: str) -> bool:
    name = str(value or "").casefold().strip()
    return (
        name in BROAD_SCOPE_NAMES
        or name.startswith("__")
        or name.endswith("_workspace")
        or name.endswith("_root")
    )


def infer_sub_scope(cwd: str | None, texts: list[str]) -> dict[str, Any]:
    candidates: list[tuple[str, str]] = []
    if cwd:
        leaf = str(cwd).replace("\\", "/").rstrip("/").split("/")[-1]
        if leaf and not is_broad_scope_name(leaf):
            candidates.append((leaf, "cwd_leaf"))
    combined = "\n".join(texts)
    for path in PATH_RE.findall(combined):
        parts = [part for part in path.replace("\\", "/").split("/") if part]
        for part in reversed(parts):
            compact = part.strip()
            if compact and not is_broad_scope_name(compact) and REPO_LIKE_RE.fullmatch(compact):
                candidates.append((compact, "path_mention"))
                break
    for match in REPO_LIKE_RE.findall(combined):
        if not is_broad_scope_name(match):
            candidates.append((match, "text_mention"))
    if not candidates:
        return {
            "inferred_sub_scope": None,
            "sub_scope_candidates": [],
            "sub_scope_source": None,
            "sub_scope_confidence": "none",
        }
    counts: dict[str, tuple[int, str]] = {}
    for candidate, source in candidates:
        key = candidate.strip()
        current = counts.get(key, (0, source))
        counts[key] = (current[0] + 1, current[1])
    label, (count, source) = sorted(counts.items(), key=lambda pair: (-pair[1][0], pair[0].casefold()))[0]
    return {
        "inferred_sub_scope": label,
        "sub_scope_candidates": [item[0] for item in sorted(counts.items(), key=lambda pair: (-pair[1][0], pair[0].casefold()))[:5]],
        "sub_scope_source": source,
        "sub_scope_confidence": "medium" if count > 1 or source in {"cwd_leaf", "path_mention"} else "low",
    }


def build_session_display_label(session: dict[str, Any], messages: list[Any]) -> dict[str, Any]:
    operational = first_operational_input(messages)
    operational_text = operational["text"]
    scope = infer_sub_scope(session.get("cwd"), [operational_text])
    external_session_id = session.get("external_session_id") or f"session-{session.get('id')}"
    if operational_text:
        prefix = scope.get("inferred_sub_scope") or external_session_id
        return {
            **scope,
            "display_label": _compact(f"{prefix} · {operational_text}", limit=120),
            "label_source": operational["source"],
            "label_quality": "medium" if operational["source"] != "fallback" else "low",
            "first_operational_input_preview": _compact(operational_text, limit=180),
            "internal_prompt_suppressed": bool(operational["internal_prompt_suppressed"]),
            "low_value_session": False,
            "low_value_reason": None,
        }
    return {
        **scope,
        "display_label": _compact(str(external_session_id), limit=120),
        "label_source": "fallback",
        "label_quality": "low",
        "first_operational_input_preview": "",
        "internal_prompt_suppressed": bool(operational["internal_prompt_suppressed"]),
        "low_value_session": bool(operational["internal_prompt_suppressed"]),
        "low_value_reason": "internal_title_generation_prompt" if operational["internal_prompt_suppressed"] else None,
    }


def capture_version_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    for key in ("producer_version", "server_version", "package_version"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return {
                "producer_version": value.strip(),
                "capture_version_status": "known_session_metadata",
                "capture_version_scope": "session",
                "capture_version_inferred": False,
            }
    return {
        "producer_version": None,
        "capture_version_status": "unknown",
        "capture_version_scope": "none",
        "capture_version_inferred": False,
    }
