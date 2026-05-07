from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any


WINDOWS_ABS_RE = re.compile(r"[A-Za-z]:[\\/][^\s`\"<>|]+")
POSIX_ABS_RE = re.compile(r"(?<!\w)/(?:[^\s`\"<>|]+/)*[^\s`\"<>|]+")
SCOPE_RE = re.compile(r"^\s*Scope:\s*`?([^`\r\n]+)`?\s*$", re.IGNORECASE | re.MULTILINE)
CODEX_AGENT_MEM_GENERATED_CONTEXT_RE = re.compile(
    r"<!--\s*codex-agent-mem:generated-context:start\s*-->.*?"
    r"(?:<!--\s*codex-agent-mem:generated-context:end\s*-->|$)",
    re.IGNORECASE | re.DOTALL,
)
CANONICAL_RE = re.compile(
    r"Nombre\s+canonico:\s*(?:\r?\n\s*-\s*)?`?([^`\r\n]+)`?",
    re.IGNORECASE,
)
PAYLOAD_PROJECT_KEY_FIELDS = (
    "project_key",
    "project-key",
    "project_name",
    "project-name",
    "workspace_key",
    "workspace-key",
    "workspace_name",
    "workspace-name",
)

PROJECT_MARKERS = (
    ".git",
    "AGENTS.md",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
)
TECHNICAL_NAMES = {
    "",
    "system32",
    "syswow64",
    "windows",
    "winnt",
    "temp",
    "tmp",
    "program files",
    "program files (x86)",
}


@dataclass(frozen=True)
class ProjectIdentity:
    project_key: str
    root_path: str | None = None
    source: str = "fallback"
    confidence: str = "low"
    warnings: list[str] = field(default_factory=list)


def resolve_project_identity(
    payload: dict[str, Any],
    *,
    explicit: str | None = None,
    project_from_cwd: bool = False,
) -> ProjectIdentity:
    if explicit:
        return ProjectIdentity(
            project_key=explicit,
            root_path=_payload_cwd(payload),
            source="explicit",
            confidence="high",
        )

    payload_project_key = _payload_project_key(payload)
    if payload_project_key:
        return ProjectIdentity(
            project_key=payload_project_key,
            root_path=_payload_cwd(payload),
            source="payload_project_key",
            confidence="high",
        )

    warnings: list[str] = []
    cwd = _payload_cwd(payload)
    if project_from_cwd and cwd:
        cwd_identity = _identity_from_path(cwd, source="cwd")
        if cwd_identity and cwd_identity.confidence != "low":
            return _with_added_warnings(
                cwd_identity,
                _ignored_mentioned_path_warnings(payload, selected_project_key=cwd_identity.project_key),
            )
        if _is_technical_path(cwd):
            warnings.append("technical_cwd_ignored")
            return ProjectIdentity(
                project_key="default-project",
                root_path=None,
                source="fallback",
                confidence="low",
                warnings=warnings,
            )
        warnings.append("cwd_did_not_resolve_to_project")
        for raw_path in _mentioned_paths_within_cwd(payload, cwd):
            identity = _identity_from_path(raw_path, source="mentioned_path")
            if identity:
                return _with_added_warnings(identity, warnings)
        if cwd_identity:
            return _with_added_warnings(cwd_identity, warnings)
        return ProjectIdentity(
            project_key="default-project",
            root_path=None,
            source="fallback",
            confidence="low",
            warnings=warnings,
        )

    for raw_path in _mentioned_paths(payload):
        identity = _identity_from_path(raw_path, source="mentioned_path")
        if identity:
            return identity

    return ProjectIdentity(
        project_key="default-project",
        root_path=None,
        source="fallback",
        confidence="low",
        warnings=warnings,
    )


def _payload_cwd(payload: dict[str, Any]) -> str | None:
    cwd = payload.get("cwd") or payload.get("cwd_path")
    return str(cwd) if cwd else None


def _payload_project_key(payload: dict[str, Any]) -> str | None:
    for key_field in PAYLOAD_PROJECT_KEY_FIELDS:
        value = payload.get(key_field)
        if not isinstance(value, str):
            continue
        key = value.strip()
        if _is_usable_project_key(key):
            return key
    return None


def _mentioned_paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for text in _payload_texts(payload):
        for match in [*WINDOWS_ABS_RE.findall(text), *POSIX_ABS_RE.findall(text)]:
            cleaned = _strip_path_punctuation(match)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                paths.append(cleaned)
    return paths


def _mentioned_paths_within_cwd(payload: dict[str, Any], cwd: str) -> list[str]:
    return [path for path in _mentioned_paths(payload) if _path_is_within(path, cwd)]


def _ignored_mentioned_path_warnings(
    payload: dict[str, Any],
    *,
    selected_project_key: str,
) -> list[str]:
    for raw_path in _mentioned_paths(payload):
        identity = _identity_from_path(raw_path, source="mentioned_path")
        if identity and identity.project_key != selected_project_key:
            return ["mentioned_path_ignored_due_to_cwd_project"]
    return []


def _with_added_warnings(identity: ProjectIdentity, warnings: list[str]) -> ProjectIdentity:
    if not warnings:
        return identity
    merged = [*identity.warnings]
    for warning in warnings:
        if warning not in merged:
            merged.append(warning)
    return ProjectIdentity(
        project_key=identity.project_key,
        root_path=identity.root_path,
        source=identity.source,
        confidence=identity.confidence,
        warnings=merged,
    )


def _payload_texts(payload: dict[str, Any]) -> list[str]:
    values = [
        payload.get("input-messages"),
        payload.get("input_messages"),
        payload.get("input"),
        payload.get("prompt"),
        payload.get("request"),
        payload.get("user-message"),
        payload.get("user_message"),
        payload.get("last-assistant-message"),
        payload.get("last_assistant_message"),
        payload.get("assistant-response"),
        payload.get("assistant_response"),
        payload.get("response"),
        payload.get("output"),
    ]
    texts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, list):
            texts.extend(_text_from_item(item) for item in value)
        else:
            texts.append(_text_from_item(value))
    return [text for text in texts if text]


def _text_from_item(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if isinstance(item.get("text"), str):
            return item["text"]
        if isinstance(item.get("content"), str):
            return item["content"]
    return str(item)


def _strip_path_punctuation(path: str) -> str:
    return path.strip().rstrip(".,;:)]}'\"")


def _identity_from_path(raw_path: str, *, source: str) -> ProjectIdentity | None:
    if _is_technical_path(raw_path):
        return None

    start = _existing_start_path(raw_path)
    if start is not None:
        for current in _candidate_roots(start):
            scope = _scope_from_agents(current)
            if scope:
                return ProjectIdentity(
                    project_key=scope,
                    root_path=str(current),
                    source=f"{source}:AGENTS.md",
                    confidence="high",
                )
            canonical = _canonical_from_project_state(current)
            if canonical:
                return ProjectIdentity(
                    project_key=canonical,
                    root_path=str(current),
                    source=f"{source}:PROJECTS_STATE",
                    confidence="high",
                )
            if _has_project_marker(current):
                key = current.name.strip()
                if _is_usable_project_key(key):
                    return ProjectIdentity(
                        project_key=key,
                        root_path=str(current),
                        source=f"{source}:project_marker",
                        confidence="medium",
                    )

    key = _leaf_name(raw_path)
    if _is_usable_project_key(key):
        return ProjectIdentity(
            project_key=key,
            root_path=str(start) if start is not None else None,
            source=f"{source}:leaf",
            confidence="low",
        )
    return None


def _existing_start_path(raw_path: str) -> Path | None:
    try:
        path = Path(raw_path)
    except (OSError, ValueError):
        return None
    if path.exists():
        return path if path.is_dir() else path.parent
    for parent in path.parents:
        if parent.exists():
            return parent
    return None


def _candidate_roots(start: Path) -> list[Path]:
    return [start, *list(start.parents)][:10]


def _path_is_within(raw_path: str, root_path: str) -> bool:
    try:
        child = Path(raw_path).resolve(strict=False)
        root = Path(root_path).resolve(strict=False)
        return child == root or root in child.parents
    except (OSError, RuntimeError, ValueError):
        child_text = str(raw_path).replace("/", "\\").rstrip("\\").casefold()
        root_text = str(root_path).replace("/", "\\").rstrip("\\").casefold()
        return bool(root_text) and (child_text == root_text or child_text.startswith(root_text + "\\"))


def _scope_from_agents(root: Path) -> str | None:
    path = root / "AGENTS.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    text = CODEX_AGENT_MEM_GENERATED_CONTEXT_RE.sub("", text)
    match = SCOPE_RE.search(text)
    if not match:
        return None
    key = match.group(1).strip()
    return key if _is_usable_project_key(key) else None


def _canonical_from_project_state(root: Path) -> str | None:
    for path in sorted(root.glob("PROJECTS_STATE_*.md"))[:3]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        key = _canonical_from_project_state_text(text)
        if key:
            return key
    return None


def _canonical_from_project_state_text(text: str) -> str | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r"Nombre\s+canonico", line, re.IGNORECASE):
            continue
        for candidate in lines[index + 1 : index + 8]:
            cleaned = candidate.strip()
            if not cleaned:
                continue
            if cleaned.startswith("-"):
                cleaned = cleaned[1:].strip()
            cleaned = cleaned.strip("` ")
            if _is_usable_project_key(cleaned):
                return cleaned
        match = CANONICAL_RE.search(text)
        if match:
            key = match.group(1).strip().strip("` ")
            if _is_usable_project_key(key):
                return key
    match = CANONICAL_RE.search(text)
    if match:
        key = match.group(1).strip().strip("` ")
        if _is_usable_project_key(key):
            return key
    return None


def _has_project_marker(root: Path) -> bool:
    return any((root / marker).exists() for marker in PROJECT_MARKERS)


def _leaf_name(raw_path: str) -> str:
    if re.match(r"^[A-Za-z]:[\\/]", raw_path):
        return PureWindowsPath(raw_path).name.strip()
    return Path(raw_path).name.strip()


def _is_usable_project_key(key: str) -> bool:
    normalized = key.strip().casefold()
    return bool(normalized) and normalized not in TECHNICAL_NAMES


def _is_technical_path(raw_path: str) -> bool:
    normalized = raw_path.replace("/", "\\").strip().casefold()
    leaf = _leaf_name(raw_path).casefold()
    return (
        leaf in TECHNICAL_NAMES
        or "\\windows\\system32" in normalized
        or normalized.endswith("\\windows")
    )
