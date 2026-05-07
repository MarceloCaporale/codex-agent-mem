from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from time import perf_counter
from typing import Any

from codex_agent_mem import __version__
from codex_agent_mem.closure_control import build_completion_check, build_open_work_report
from codex_agent_mem.context_pack import build_context_pack, choose_auto_budget
from codex_agent_mem.health import build_health_report
from codex_agent_mem.ingest import classify_event, stable_hash
from codex_agent_mem.models import GenericEventEnvelope, Observation
from codex_agent_mem.operational_state import STATEFUL_OBSERVATION_TYPES, derive_operational_state
from codex_agent_mem.policy_engine import (
    evaluate_policy_effects,
    filter_items_by_policy,
    selector_matches,
    sort_items_for_priority,
    validate_inheritance_definition,
    validate_policy_definition,
)
from codex_agent_mem.retrieval_hygiene import (
    build_session_display_label,
    cap_items_per_session,
    capture_version_from_metadata,
    dedupe_retrieval_items,
    infer_sub_scope,
    is_broad_scope_name,
    is_internal_prompt_noise,
    item_text,
    session_matches_query,
)
from codex_agent_mem.scope_control import build_recent_changes, build_scope_guard

RETRIEVAL_TYPE_PRIORITY = {
    "pending_item": 0,
    "blocker": 1,
    "project_dod": 2,
    "mission_dod": 2,
    "session_dod": 2,
    "objective": 3,
    "constraint": 3,
    "user_request": 3,
    "decision": 4,
    "completed_item": 5,
    "completion_claim": 6,
    "session_summary": 7,
}
MEANINGFUL_CHANGE_TYPES = sorted(STATEFUL_OBSERVATION_TYPES - {"user_request"})
MANUAL_NOTE_HIGH_VALUE_TAGS = {
    "baseline",
    "blocker",
    "current-state",
    "decision",
    "freeze",
    "governance",
    "installation-state",
    "publish-hold",
    "release",
    "roadmap",
    "version-state",
}
MANUAL_NOTE_EXCLUDED_STATUSES = {"low_value", "retired", "superseded"}
MANUAL_NOTE_STOPWORDS = {
    "a",
    "al",
    "and",
    "con",
    "de",
    "del",
    "el",
    "en",
    "for",
    "la",
    "las",
    "los",
    "of",
    "on",
    "para",
    "por",
    "the",
    "to",
    "un",
    "una",
    "y",
}
MANUAL_NOTE_GENERIC_QUERY_TOKENS = {
    "audit",
    "auditoria",
    "auditorias",
    "auditar",
    "code",
    "codigo",
    "doc",
    "docs",
    "documento",
    "documentos",
    "manifest",
    "manifiesto",
    "package",
    "packages",
    "paquete",
    "paquetes",
    "plan",
    "planes",
    "pro",
    "report",
    "reporte",
    "reportes",
    "reports",
    "roadmap",
    "roadmaps",
}
MANUAL_NOTE_META_TAGS = {
    "local-install",
    "manual-note-search",
    "mcp-internal",
    "relevance-gate",
    "test",
    "validation",
}
MANUAL_NOTE_META_QUERY_TOKENS = {
    "debug",
    "diagnostic",
    "gate",
    "install",
    "internal",
    "local",
    "manual",
    "meta",
    "note",
    "relevance",
    "search",
    "smoke",
    "test",
    "validation",
}
MANUAL_NOTE_ALIAS_GROUPS = (
    {
        "bloqueada",
        "bloqueado",
        "cierre",
        "congelada",
        "congelado",
        "freeze",
        "frozen",
        "hold",
    },
    {"github", "publicacion", "publicar", "publish", "release"},
    {"site", "sitio", "sitios", "website", "websites"},
)
MANUAL_NOTE_TAG_QUERY_GROUPS = {
    "baseline": {"actual", "baseline", "current", "estado", "state", "version"},
    "blocker": {"blocker", "bloqueada", "bloqueado", "bloqueante", "bloqueo", "pendiente", "pendientes"},
    "current-state": {"actual", "current", "estado", "state", "version"},
    "decision": {"autorizacion", "decision", "decidir", "explicit", "final"},
    "freeze": {"bloqueada", "bloqueado", "cierre", "congelada", "congelado", "freeze", "frozen", "hold"},
    "governance": {"gobernanza", "governance", "policy", "protocolo"},
    "installation-state": {"instalada", "instalado", "instalacion", "installation", "local", "runtime"},
    "publish-hold": {
        "assets",
        "checksums",
        "github",
        "hold",
        "publicacion",
        "publicar",
        "publish",
        "release",
        "tag",
    },
    "release": {"assets", "checksums", "github", "publicacion", "publicar", "publish", "release", "tag"},
    "roadmap": {"plan", "planes", "roadmap", "roadmaps"},
    "version-state": {"actual", "baseline", "estado", "instalada", "instalado", "version"},
}
MANUAL_NOTE_STABLE_SIGNAL_PHRASES = (
    "baseline",
    "do not publish",
    "do not touch",
    "explicit approval",
    "final decision",
    "freeze tecnico",
    "frozen assets",
    "hashes",
    "human diff ready",
    "installed version",
    "publish pending",
    "release hold",
)
RECOMMENDED_NARROWING_EXCLUDED_CANDIDATES = {
    "ambient",
    "appdata",
    "classifier",
    "local",
    "policy",
    "policy-classifier",
    "policy-safety",
    "program-files",
    "program-files-x86",
    "programdata",
    "roaming",
    "safety",
    "safety-classifier",
    "self-harm",
    "system32",
    "temp",
    "tmp",
    "users",
    "windows",
}


def _path_is_within_root(path_value: Any, root_value: Any) -> bool:
    if not path_value or not root_value:
        return True
    try:
        path = Path(str(path_value)).resolve(strict=False)
        root = Path(str(root_value)).resolve(strict=False)
        return path == root or root in path.parents
    except (OSError, RuntimeError, ValueError):
        path_text = str(path_value).replace("/", "\\").rstrip("\\").casefold()
        root_text = str(root_value).replace("/", "\\").rstrip("\\").casefold()
        return bool(root_text) and (path_text == root_text or path_text.startswith(root_text + "\\"))


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def bootstrap(conn: sqlite3.Connection, schema_sql: str) -> None:
    conn.executescript(schema_sql)
    _ensure_schema_columns(conn)
    conn.commit()


def _ensure_schema_columns(conn: sqlite3.Connection) -> None:
    context_sync_columns = {row["name"] for row in conn.execute("PRAGMA table_info(context_sync_events)").fetchall()}
    if "budget" not in context_sync_columns:
        conn.execute("ALTER TABLE context_sync_events ADD COLUMN budget TEXT NOT NULL DEFAULT 'normal'")
    if "budget_reason" not in context_sync_columns:
        conn.execute("ALTER TABLE context_sync_events ADD COLUMN budget_reason TEXT")
    if "build_ms" not in context_sync_columns:
        conn.execute("ALTER TABLE context_sync_events ADD COLUMN build_ms REAL NOT NULL DEFAULT 0")


def _type_priority_case(column: str = "o.type") -> str:
    clauses = [f"WHEN '{name}' THEN {priority}" for name, priority in RETRIEVAL_TYPE_PRIORITY.items()]
    return f"CASE {column} {' '.join(clauses)} ELSE 50 END"


def _fold_search_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text.replace("_", "-")).strip()


def _search_tokens(value: Any) -> set[str]:
    folded = _fold_search_text(value).replace("-", " ")
    return {token for token in re.findall(r"[a-z0-9]+", folded) if token}


def _tag_key(value: Any) -> str:
    folded = _fold_search_text(value)
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


def _manual_note_tags_from_detail(detail: Any) -> list[str]:
    tags: list[str] = []
    for line in str(detail or "").splitlines():
        if not line.casefold().strip().startswith("tags:"):
            continue
        raw_tags = line.split(":", 1)[1].split(",")
        for raw_tag in raw_tags:
            tag = " ".join(raw_tag.split())
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def _expanded_query_tokens(query_tokens: set[str]) -> set[str]:
    expanded = set(query_tokens)
    for alias_group in MANUAL_NOTE_ALIAS_GROUPS:
        if query_tokens & alias_group:
            expanded.update(alias_group)
    return expanded


def _strong_query_tokens(query_tokens: set[str]) -> set[str]:
    return {token for token in query_tokens if len(token) > 1 and not token.isdigit()}


def _meaningful_query_tokens(query_tokens: set[str]) -> set[str]:
    strong_tokens = _strong_query_tokens(query_tokens)
    return strong_tokens - MANUAL_NOTE_STOPWORDS - MANUAL_NOTE_GENERIC_QUERY_TOKENS


def _tag_components(tag: str) -> set[str]:
    return _meaningful_query_tokens(_search_tokens(tag))


def _single_opaque_identifier_query(query: str) -> str | None:
    raw_query = str(query or "").strip()
    if not raw_query or re.search(r"\s", raw_query):
        return None
    if len(raw_query) < 8:
        return None
    if not re.search(r"\d", raw_query):
        return None
    if not re.search(r"[_:.-]", raw_query):
        return None
    folded = _fold_search_text(raw_query)
    return folded or None


def _recommended_narrowing_candidate(value: Any) -> str | None:
    candidate = str(value or "").strip().strip("\"'`")
    if not candidate:
        return None
    candidate = candidate.replace("\\", "/").rstrip("/").split("/")[-1]
    if not candidate or len(candidate) > 96:
        return None
    if candidate != candidate.casefold():
        return None
    folded = _fold_search_text(candidate)
    if folded in RECOMMENDED_NARROWING_EXCLUDED_CANDIDATES:
        return None
    if "classifier" in folded and ("policy" in folded or "safety" in folded):
        return None
    if is_broad_scope_name(candidate):
        return None
    if candidate.endswith("_lab"):
        return None
    if "-" not in candidate and "_" not in candidate:
        return None
    if any(ch.isspace() for ch in candidate):
        return None
    if any(not (ch.isalnum() or ch in {"-", "_", "."}) for ch in candidate):
        return None
    return candidate


def _scope_path_leaf(value: Any) -> str | None:
    text = str(value or "").strip().strip("\"'`")
    if not text:
        return None
    return text.replace("\\", "/").rstrip("/").split("/")[-1] or None


def _scope_hint_text(
    hint: str | None = None,
    *,
    current_cwd: str | None = None,
    repo_path: str | None = None,
    mentioned_files: list[str] | None = None,
) -> str:
    parts: list[str] = []
    for value in (hint, current_cwd, repo_path):
        text = " ".join(str(value or "").split())
        if text:
            parts.append(text)
            leaf = _scope_path_leaf(text)
            if leaf and leaf != text:
                parts.append(leaf)
    for value in mentioned_files or []:
        text = " ".join(str(value or "").split())
        if text:
            parts.append(text)
            leaf = _scope_path_leaf(text)
            if leaf and leaf != text:
                parts.append(leaf)
    return " ".join(parts)


def _combine_scope_hints(*values: str | None) -> str | None:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(str(value or "").split())
        if not text:
            continue
        folded = _fold_search_text(text)
        if folded in seen:
            continue
        seen.add(folded)
        parts.append(text)
    return " ".join(parts) if parts else None


def _scope_confidence(top_score: int, second_score: int = 0) -> str:
    if top_score >= 150 and top_score >= second_score + 45:
        return "high"
    if top_score >= 70:
        return "medium"
    return "low"


def _scope_lane_inventory(
    source_items: list[dict[str, Any]],
    *,
    second_score: int = 0,
    limit: int = 8,
) -> list[dict[str, Any]]:
    lanes: dict[str, dict[str, Any]] = {}
    for item in source_items:
        lane = _recommended_narrowing_candidate(item.get("inferred_sub_scope")) or _recommended_narrowing_candidate(
            item.get("cwd")
        )
        if not lane:
            continue
        session_id = item.get("session_id") if item.get("session_id") is not None else item.get("id")
        bucket = lanes.setdefault(
            lane,
            {
                "inferred_sub_scope": lane,
                "session_count": 0,
                "session_ids": [],
                "external_session_ids": [],
                "latest_turn_at": None,
                "top_score": 0,
                "confidence": "low",
                "signals_used": set(),
                "matched_tokens": set(),
                "recommended_call": f'mem_session_list(project_key, query="{lane}")',
            },
        )
        bucket["session_count"] += 1
        if session_id is not None and len(bucket["session_ids"]) < 8:
            bucket["session_ids"].append(int(session_id))
        external_session_id = item.get("external_session_id")
        if external_session_id and len(bucket["external_session_ids"]) < 8:
            bucket["external_session_ids"].append(str(external_session_id))
        last_turn_at = str(item.get("last_turn_at") or "")
        if last_turn_at and (bucket["latest_turn_at"] is None or last_turn_at > str(bucket["latest_turn_at"])):
            bucket["latest_turn_at"] = last_turn_at
        score = int(item.get("score") or 0)
        if score > int(bucket["top_score"]):
            bucket["top_score"] = score
        bucket["signals_used"].update(str(signal) for signal in item.get("signals_used") or [])
        bucket["matched_tokens"].update(str(token) for token in item.get("matched_tokens") or [])

    results: list[dict[str, Any]] = []
    for bucket in lanes.values():
        top_score = int(bucket["top_score"])
        results.append(
            {
                "inferred_sub_scope": bucket["inferred_sub_scope"],
                "session_count": int(bucket["session_count"]),
                "session_ids": bucket["session_ids"],
                "external_session_ids": bucket["external_session_ids"],
                "latest_turn_at": bucket["latest_turn_at"],
                "top_score": top_score,
                "confidence": _scope_confidence(top_score, second_score) if top_score else "low",
                "signals_used": sorted(bucket["signals_used"]),
                "matched_tokens": sorted(bucket["matched_tokens"]),
                "recommended_call": bucket["recommended_call"],
            }
        )
    results.sort(
        key=lambda item: (
            int(item["top_score"]),
            str(item.get("latest_turn_at") or ""),
            int(item["session_count"]),
            str(item["inferred_sub_scope"]),
        ),
        reverse=True,
    )
    return results[: max(1, min(int(limit), 20))]


class CodexAgentMemStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = connect(db_path)
        schema_sql = files("codex_agent_mem").joinpath("schema.sql").read_text(encoding="utf-8")
        bootstrap(self.conn, schema_sql)

    def close(self) -> None:
        conn = getattr(self, "conn", None)
        if conn is None:
            return
        self.conn = None
        conn.close()

    def set_query_only(self, enabled: bool = True) -> None:
        self.conn.execute(f"PRAGMA query_only={'ON' if enabled else 'OFF'};")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _project_name(project_key: str) -> str:
        return project_key.replace("-", " ").replace("_", " ").strip() or project_key

    @staticmethod
    def _root_path_key(root_path: str | None) -> str:
        if not root_path:
            return ""
        text = str(root_path).strip()
        if not text:
            return ""
        try:
            text = str(Path(text).resolve(strict=False))
        except (OSError, RuntimeError, ValueError):
            pass
        return text.replace("/", "\\").rstrip("\\").casefold()

    @staticmethod
    def _snapshot_slug(label: str) -> str:
        compact = "".join(ch.lower() if ch.isalnum() else "-" for ch in label).strip("-")
        while "--" in compact:
            compact = compact.replace("--", "-")
        return compact[:48] or "snapshot"

    @staticmethod
    def _load_json(raw: str | None, fallback: Any) -> Any:
        if not raw:
            return fallback
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return fallback

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            normalized = str(value)
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None

    @classmethod
    def _memory_age_seconds(cls, value: str | None) -> int | None:
        parsed = cls._parse_timestamp(value)
        if parsed is None:
            return None
        return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))

    def _snapshot_dir(self) -> Path:
        path = self.db_path.parent / "snapshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _model_name_from_event(event: GenericEventEnvelope) -> str | None:
        metadata = event.metadata or {}
        for key in ("model_name", "model", "llm_model"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def upsert_project(self, project_key: str, root_path: str | None) -> int:
        now = self._now()
        name = self._project_name(project_key)
        incoming_root = str(root_path).strip() if root_path else None
        with self.conn:
            existing = self.conn.execute(
                "SELECT id, root_path FROM projects WHERE project_key = ?",
                (project_key,),
            ).fetchone()
            if existing is None:
                cur = self.conn.execute(
                    """
                    INSERT INTO projects(project_key, name, root_path, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (project_key, name, incoming_root, now, now),
                )
                return int(cur.lastrowid)
            existing_root = existing["root_path"]
            if (
                incoming_root
                and (
                    not existing_root
                    or self._root_path_key(existing_root) == self._root_path_key(incoming_root)
                )
            ):
                next_root = incoming_root
            else:
                next_root = existing_root
            self.conn.execute(
                """
                UPDATE projects
                SET name = ?, root_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, next_root, now, int(existing["id"])),
            )
            return int(existing["id"])

    def _session_metadata_for_upsert(self, project_id: int, event: GenericEventEnvelope) -> dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT metadata_json
            FROM sessions
            WHERE project_id = ? AND runtime = ? AND external_session_id = ?
            """,
            (project_id, event.runtime, event.session_id),
        ).fetchone()
        existing = self._load_json(row["metadata_json"], {}) if row is not None else {}
        if not isinstance(existing, dict):
            existing = {}
        incoming = dict(event.metadata or {})
        metadata = dict(existing)
        for key, value in incoming.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            metadata[key] = value

        first_seen = (
            existing.get("producer_version_first_seen")
            or existing.get("producer_version")
            or incoming.get("producer_version")
            or __version__
        )
        metadata["producer_version_first_seen"] = str(first_seen)
        metadata["producer_version_last_seen"] = __version__
        metadata["producer_version"] = __version__
        metadata["server_version"] = __version__
        metadata["package_version"] = __version__
        try:
            existing_schema_version = int(existing.get("capture_schema_version") or 0)
        except (TypeError, ValueError):
            existing_schema_version = 0
        try:
            incoming_schema_version = int(incoming.get("capture_schema_version") or 0)
        except (TypeError, ValueError):
            incoming_schema_version = 0
        metadata["capture_schema_version"] = max(1, existing_schema_version, incoming_schema_version)
        return metadata

    def upsert_session(self, project_id: int, event: GenericEventEnvelope) -> int:
        metadata = self._session_metadata_for_upsert(project_id, event)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sessions(project_id, runtime, external_session_id, started_at, cwd, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, runtime, external_session_id) DO UPDATE SET
                  cwd = COALESCE(excluded.cwd, sessions.cwd),
                  metadata_json = excluded.metadata_json
                """,
                (
                    project_id,
                    event.runtime,
                    event.session_id,
                    event.timestamp,
                    event.cwd,
                    self._json(metadata),
                ),
            )
        row = self.conn.execute(
            "SELECT id FROM sessions WHERE project_id = ? AND runtime = ? AND external_session_id = ?",
            (project_id, event.runtime, event.session_id),
        ).fetchone()
        assert row is not None
        return int(row["id"])

    def upsert_turn(self, session_id: int, raw_payload: dict[str, Any], event: GenericEventEnvelope) -> tuple[int, bool]:
        content_hash = stable_hash(raw_payload)
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT OR IGNORE INTO turns(
                  session_id, external_turn_id, captured_at, input_messages_json,
                  assistant_message, tool_events_json, raw_payload_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    event.turn_id,
                    event.timestamp,
                    self._json(event.input_messages),
                    event.assistant_message,
                    self._json(event.tool_events),
                    self._json(raw_payload),
                    content_hash,
                ),
            )
        row = self.conn.execute(
            "SELECT id FROM turns WHERE session_id = ? AND external_turn_id = ?",
            (session_id, event.turn_id),
        ).fetchone()
        assert row is not None
        return int(row["id"]), bool(cur.rowcount)

    def _dedupe_hash(self, project_id: int, session_id: int, turn_id: int, obs: Observation) -> str:
        raw = "|".join(
            [
                str(project_id),
                str(session_id),
                str(turn_id),
                obs.type,
                obs.title,
                obs.summary,
                obs.detail,
            ]
        ).encode("utf-8")
        return sha256(raw).hexdigest()

    def _turn_content_hash(self, turn_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT content_hash FROM turns WHERE id = ?",
            (turn_id,),
        ).fetchone()
        return str(row["content_hash"]) if row is not None and row["content_hash"] else None

    def _latest_turn_source(self, project_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT
              t.id AS turn_id,
              s.id AS session_id,
              s.cwd,
              s.metadata_json,
              t.content_hash
            FROM turns t
            JOIN sessions s ON s.id = t.session_id
            WHERE s.project_id = ?
            ORDER BY t.captured_at DESC, t.id DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        item = dict(row)
        metadata = self._load_json(item.get("metadata_json"), {})
        model_name = None
        for key in ("model_name", "model", "llm_model"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                model_name = value.strip()
                break
        item["model_name"] = model_name
        return item

    def _session_latest_turn_source(self, session_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT
              t.id AS turn_id,
              s.id AS session_id,
              s.cwd,
              s.metadata_json,
              t.content_hash
            FROM turns t
            JOIN sessions s ON s.id = t.session_id
            WHERE s.id = ?
            ORDER BY t.captured_at DESC, t.id DESC
            LIMIT 1
            """,
            (int(session_id),),
        ).fetchone()
        if row is None:
            return None
        item = dict(row)
        metadata = self._load_json(item.get("metadata_json"), {})
        model_name = None
        for key in ("model_name", "model", "llm_model"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                model_name = value.strip()
                break
        item["model_name"] = model_name
        return item

    def record_provenance(
        self,
        *,
        memory_kind: str,
        memory_id: int,
        project_id: int,
        session_id: int | None,
        turn_id: int | None,
        observation_id: int | None,
        turn_hash: str | None,
        model_name: str | None,
        cwd: str | None,
        source_span: dict[str, Any] | None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO memory_provenance(
                  memory_kind, memory_id, project_id, session_id, turn_id, observation_id,
                  turn_hash, model_name, cwd, source_span_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_kind,
                    memory_id,
                    project_id,
                    session_id,
                    turn_id,
                    observation_id,
                    turn_hash,
                    model_name,
                    cwd,
                    self._json(source_span or {}),
                    self._now(),
                ),
            )

    def upsert_observation(self, project_id: int, session_id: int, turn_id: int, event: GenericEventEnvelope, obs: Observation) -> int:
        now = self._now()
        dedupe_hash = self._dedupe_hash(project_id, session_id, turn_id, obs)
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT OR IGNORE INTO observations(
                  project_id, session_id, turn_id, type, title, summary, detail,
                  confidence, importance, status, source_runtime, source_kind,
                  dedupe_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    session_id,
                    turn_id,
                    obs.type,
                    obs.title,
                    obs.summary,
                    obs.detail,
                    obs.confidence,
                    obs.importance,
                    obs.status,
                    event.runtime,
                    "turn_extract",
                    dedupe_hash,
                    now,
                    now,
                ),
            )
        row = self.conn.execute("SELECT id FROM observations WHERE dedupe_hash = ?", (dedupe_hash,)).fetchone()
        assert row is not None
        obs_id = int(row["id"])
        if cur.rowcount:
            for file_path in obs.files:
                with self.conn:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO observation_files(observation_id, file_path) VALUES (?, ?)",
                        (obs_id, file_path),
                    )
            if obs.type == "decision":
                with self.conn:
                    self.conn.execute(
                        """
                        INSERT OR IGNORE INTO decisions(
                          project_id, source_observation_id, title, decision_text, status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            project_id,
                            obs_id,
                            obs.title,
                            obs.summary,
                            obs.status,
                            now,
                            now,
                        ),
                    )
            self.record_provenance(
                memory_kind="observation",
                memory_id=obs_id,
                project_id=project_id,
                session_id=session_id,
                turn_id=turn_id,
                observation_id=obs_id,
                turn_hash=self._turn_content_hash(turn_id),
                model_name=self._model_name_from_event(event),
                cwd=event.cwd,
                source_span={
                    "source_kind": "turn_extract",
                    "observation_type": obs.type,
                    "title": obs.title,
                    "files": list(obs.files),
                },
            )
        return obs_id

    def create_manual_note(
        self,
        project_key: str,
        text: str,
        *,
        session_id: int | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
        importance: int | None = None,
    ) -> dict[str, Any] | None:
        note_text = " ".join(str(text or "").split())
        if not note_text:
            raise ValueError("Note text is required")
        project = self._project_row(project_key)
        if project is None:
            self.upsert_project(project_key, None)
            project = self._project_row(project_key)
            assert project is not None
        raw_tags = [tags] if isinstance(tags, str) else (tags or [])
        normalized_tags = []
        for tag in raw_tags:
            cleaned = " ".join(str(tag).split())
            if cleaned and cleaned not in normalized_tags:
                normalized_tags.append(cleaned)
        note_title = " ".join(str(title or "").split())
        if not note_title:
            note_title = f"Manual note: {note_text[:80]}".rstrip()
        note_importance = 3 if importance is None else max(1, min(int(importance), 5))
        resolved_session_id = (
            self._resolve_session_id(project_key, session_id=session_id)
            if session_id is not None
            else None
        )
        session = self.get_session(resolved_session_id) if resolved_session_id is not None else None
        now = self._now()
        detail_lines = [note_text]
        if normalized_tags:
            detail_lines.append("")
            detail_lines.append("Tags: " + ", ".join(normalized_tags))
        detail = "\n".join(detail_lines)
        dedupe_raw = self._json(
            {
                "kind": "manual_note",
                "project_id": int(project["id"]),
                "session_id": resolved_session_id,
                "title": note_title,
                "text": note_text,
                "tags": normalized_tags,
            }
        )
        dedupe_hash = sha256(dedupe_raw.encode("utf-8")).hexdigest()
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT OR IGNORE INTO observations(
                  project_id, session_id, turn_id, type, title, summary, detail,
                  confidence, importance, status, source_runtime, source_kind,
                  dedupe_hash, created_at, updated_at
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(project["id"]),
                    resolved_session_id,
                    "session_summary",
                    note_title,
                    note_text,
                    detail,
                    1.0,
                    note_importance,
                    "active",
                    "mcp",
                    "manual_note",
                    dedupe_hash,
                    now,
                    now,
                ),
            )
            created = bool(cur.rowcount)
            if created:
                self.conn.execute(
                    "UPDATE projects SET updated_at = ? WHERE id = ?",
                    (now, int(project["id"])),
                )
        row = self.conn.execute("SELECT id, created_at FROM observations WHERE dedupe_hash = ?", (dedupe_hash,)).fetchone()
        assert row is not None
        observation_id = int(row["id"])
        provenance_confidence = "high" if resolved_session_id is not None else "project"
        provenance_warning = (
            None
            if resolved_session_id is not None
            else "No session_id was provided; note is project-scoped and not associated with a specific session."
        )
        if created:
            self.record_provenance(
                memory_kind="observation",
                memory_id=observation_id,
                project_id=int(project["id"]),
                session_id=resolved_session_id,
                turn_id=None,
                observation_id=observation_id,
                turn_hash=None,
                model_name=None,
                cwd=session.get("cwd") if session else None,
                source_span={
                    "source_kind": "manual_note",
                    "title": note_title,
                    "tags": normalized_tags,
                    "importance": note_importance,
                    "provenance_confidence": provenance_confidence,
                    "provenance_warning": provenance_warning,
                    "session_id": resolved_session_id,
                    "external_session_id": session.get("external_session_id") if session else None,
                    "display_label": session.get("display_label") if session else None,
                },
            )
        return {
            "id": observation_id,
            "observation_id": observation_id,
            "created": created,
            "project_key": project_key,
            "title": note_title,
            "text": note_text,
            "tags": normalized_tags,
            "importance": note_importance,
            "type": "session_summary",
            "source_kind": "manual_note",
            "session_id": resolved_session_id,
            "external_session_id": session.get("external_session_id") if session else None,
            "cwd": session.get("cwd") if session else None,
            "project_root_path": project["root_path"],
            "display_label": session.get("display_label") if session else None,
            "provenance_confidence": provenance_confidence,
            "provenance_warning": provenance_warning,
            "created_at": row["created_at"],
        }

    def ingest_event(self, raw_payload: dict[str, Any], event: GenericEventEnvelope) -> dict[str, Any]:
        project_root_path = event.metadata.get("project_root_path")
        project_id = self.upsert_project(
            event.project_key,
            str(project_root_path) if project_root_path else event.cwd,
        )
        session_id = self.upsert_session(project_id, event)
        turn_id, inserted = self.upsert_turn(session_id, raw_payload, event)
        summary, observations = classify_event(event)
        observation_ids = [self.upsert_observation(project_id, session_id, turn_id, event, obs) for obs in observations]
        with self.conn:
            self.conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (self._now(), project_id),
            )
        if inserted:
            completion_check = self.completion_check(event.project_key)
            if completion_check and completion_check["closure_mismatch"]:
                self.record_closure_event(
                    project_key=event.project_key,
                    turn_id=turn_id,
                    event_kind="mismatch",
                    completion_check=completion_check,
                )
        return {
            "ok": True,
            "inserted_turn": inserted,
            "project_key": event.project_key,
            "session_id": event.session_id,
            "turn_id": event.turn_id,
            "turn_row_id": turn_id,
            "observation_ids": observation_ids,
            "summary": summary,
        }

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
              p.id,
              p.project_key,
              p.name,
              p.root_path,
              p.updated_at,
              (SELECT COUNT(*) FROM sessions s WHERE s.project_id = p.id) AS sessions,
              (SELECT COUNT(*) FROM turns t JOIN sessions s ON s.id = t.session_id WHERE s.project_id = p.id) AS turns,
              (SELECT COUNT(*) FROM observations o WHERE o.project_id = p.id) AS observations,
              (SELECT COUNT(*) FROM decisions d WHERE d.project_id = p.id AND d.status = 'active') AS active_decisions
            FROM projects p
            ORDER BY p.updated_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def _resolve_session_id(
        self,
        project_key: str,
        *,
        session_id: int | None = None,
        external_session_id: str | None = None,
    ) -> int | None:
        if session_id is None and not external_session_id:
            return None
        project = self._project_row(project_key)
        if project is None:
            raise ValueError("Project not found")
        if session_id is not None:
            row = self.conn.execute(
                """
                SELECT id
                FROM sessions
                WHERE project_id = ? AND id = ?
                """,
                (int(project["id"]), int(session_id)),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT id
                FROM sessions
                WHERE project_id = ? AND external_session_id = ?
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """,
                (int(project["id"]), str(external_session_id)),
            ).fetchone()
        if row is None:
            raise ValueError("Session not found for project")
        return int(row["id"])

    def _session_label_messages(self, session_id: int, first_messages: list[Any]) -> list[Any]:
        messages: list[Any] = []
        rows = self.conn.execute(
            """
            SELECT input_messages_json
            FROM turns
            WHERE session_id = ?
            ORDER BY captured_at ASC, id ASC
            LIMIT 5
            """,
            (int(session_id),),
        ).fetchall()
        for row in rows:
            loaded = self._load_json(row["input_messages_json"], [])
            if isinstance(loaded, list):
                messages.extend(loaded)
            elif loaded:
                messages.append(loaded)
        observation_rows = self.conn.execute(
            """
            SELECT title, summary, detail
            FROM observations
            WHERE session_id = ?
            ORDER BY updated_at ASC, id ASC
            LIMIT 5
            """,
            (int(session_id),),
        ).fetchall()
        for row in observation_rows:
            text = item_text(dict(row))
            if text:
                messages.append(text)
        return messages or first_messages

    def _session_preview(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        try:
            first_messages = json.loads(item.get("first_input_messages_json") or "[]")
        except json.JSONDecodeError:
            first_messages = []
        first_message = ""
        if first_messages:
            first_message = " ".join(str(first_messages[0]).split())
        item["first_input_preview"] = first_message[:180]
        item["session_id"] = item.get("id")
        metadata = CodexAgentMemStore._load_json(item.get("metadata_json"), {})
        if not isinstance(metadata, dict):
            metadata = {}
        metadata_project_root_path = metadata.get("project_root_path")
        project_root_path = metadata_project_root_path or item.get("project_root_path")
        item["project_root_path"] = project_root_path
        item["project_root_match"] = (
            _path_is_within_root(item.get("cwd"), project_root_path)
            if metadata_project_root_path
            else True
        )
        if item["project_root_match"] is False:
            source = str(metadata.get("project_resolution_source") or "")
            item["cross_project_capture_warning"] = (
                "mentioned_path_capture_cwd_outside_project_root"
                if source.startswith("mentioned_path")
                else "session_cwd_outside_project_root"
            )
        item.update(capture_version_from_metadata(metadata))
        label_messages = (
            self._session_label_messages(int(item["id"]), first_messages)
            if item.get("id") is not None
            else first_messages
        )
        item.update(build_session_display_label(item, label_messages))
        return item

    def recent_observations(
        self,
        project_key: str | None = None,
        limit: int = 10,
        *,
        session_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if project_key and session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        fetch_limit = limit if session_id is not None else min(max(limit * 5, limit + 20), 250)
        sql = """
        SELECT
          o.id,
          p.id AS project_id,
          p.project_key,
          p.root_path AS project_root_path,
          o.session_id,
          s.external_session_id,
          s.cwd,
          s.runtime,
          s.metadata_json,
          o.turn_id,
          o.type,
          o.title,
          o.summary,
          o.detail,
          o.importance,
          o.status,
          o.source_kind,
          o.updated_at,
          COALESCE(t.captured_at, o.updated_at) AS last_captured_turn_at
        FROM observations o
        JOIN projects p ON p.id = o.project_id
        LEFT JOIN sessions s ON s.id = o.session_id
        LEFT JOIN turns t ON t.id = o.turn_id
        {where}
        ORDER BY o.updated_at DESC, o.id DESC
        LIMIT ?
        """
        params: list[Any] = []
        where = ""
        filters: list[str] = []
        if project_key:
            filters.append("p.project_key = ?")
            params.append(project_key)
        if session_id is not None:
            filters.append("o.session_id = ?")
            params.append(int(session_id))
        if filters:
            where = "WHERE " + " AND ".join(filters)
        params.append(fetch_limit)
        rows = self.conn.execute(sql.format(where=where), params).fetchall()
        items = self._enrich_observation_items(
            [dict(row) for row in rows],
            session_filter_applied=session_id is not None,
            retrieval_scope="session" if session_id is not None else "project",
        )
        items = self._filter_cross_project_capture_items(items, session_filter_applied=session_id is not None)
        if not project_key:
            return items[:limit]
        excluded = self._effective_governance(project_key)["retrieval_excluded_keys"]
        return filter_items_by_policy(
            items,
            excluded_keys=excluded,
        )[:limit]

    def _enrich_observation_items(
        self,
        items: list[dict[str, Any]],
        *,
        session_filter_applied: bool,
        retrieval_scope: str,
    ) -> list[dict[str, Any]]:
        enriched_items: list[dict[str, Any]] = []
        for item in items:
            metadata = self._load_json(item.pop("metadata_json", None), {})
            if not isinstance(metadata, dict):
                metadata = {}
            enriched = dict(item)
            enriched["memory_kind"] = "observation"
            enriched["retrieval_scope"] = retrieval_scope
            enriched["session_filter_applied"] = session_filter_applied
            enriched["last_captured_turn_at"] = enriched.get("last_captured_turn_at") or enriched.get("updated_at")
            metadata_project_root_path = metadata.get("project_root_path")
            project_root_path = metadata_project_root_path or enriched.get("project_root_path")
            enriched["project_root_path"] = project_root_path
            cwd = enriched.get("cwd")
            project_root_match = (
                _path_is_within_root(cwd, project_root_path)
                if metadata_project_root_path
                else True
            )
            enriched["project_root_match"] = project_root_match
            if not project_root_match:
                source = str(metadata.get("project_resolution_source") or "")
                warning = "session_cwd_outside_project_root"
                if source.startswith("mentioned_path"):
                    warning = "mentioned_path_capture_cwd_outside_project_root"
                enriched["cross_project_capture_warning"] = warning
            if enriched.get("source_kind") == "manual_note":
                enriched["tags"] = _manual_note_tags_from_detail(enriched.get("detail"))
            enriched.update(capture_version_from_metadata(metadata))
            enriched_items.append(enriched)
        return enriched_items

    @staticmethod
    def _filter_cross_project_capture_items(
        items: list[dict[str, Any]],
        *,
        session_filter_applied: bool,
    ) -> list[dict[str, Any]]:
        if session_filter_applied:
            return items
        return [
            item
            for item in items
            if item.get("session_id") is None or item.get("project_root_match") is not False
        ]

    def _manual_note_retrieval_score(
        self,
        item: dict[str, Any],
        *,
        query: str,
        fallback_applied: bool,
    ) -> tuple[float, dict[str, Any]]:
        if item.get("source_kind") != "manual_note":
            return 0.0, {}
        status = str(item.get("status") or "").casefold()
        if status in MANUAL_NOTE_EXCLUDED_STATUSES:
            return 0.0, {}
        query_tokens = _search_tokens(query)
        if not query_tokens:
            return 0.0, {}
        tags = item.get("tags")
        if not isinstance(tags, list):
            tags = _manual_note_tags_from_detail(item.get("detail"))
        normalized_tags = {_tag_key(tag) for tag in tags if _tag_key(tag)}
        text_blob = " ".join(
            str(item.get(field) or "")
            for field in ("title", "summary", "detail")
            if item.get(field)
        )
        if tags:
            text_blob = f"{text_blob} {' '.join(str(tag) for tag in tags)}"
        folded_query = _fold_search_text(query)
        folded_title = _fold_search_text(item.get("title"))
        folded_summary = _fold_search_text(item.get("summary"))
        folded_detail = _fold_search_text(item.get("detail"))
        folded_tags = _fold_search_text(" ".join(str(tag) for tag in tags))
        folded_text_blob = _fold_search_text(text_blob)
        literal_query_match = bool(folded_query and folded_query in folded_text_blob)
        exact_title_query_match = bool(folded_query and folded_query == folded_title)
        title_literal_query_match = bool(folded_query and folded_query in folded_title)
        body_literal_query_match = bool(
            folded_query and (folded_query in folded_summary or folded_query in folded_detail)
        )
        tag_literal_query_match = bool(folded_query and folded_query in folded_tags)
        opaque_identifier_query = _single_opaque_identifier_query(query)
        exact_identifier_match = bool(
            opaque_identifier_query and re.search(rf"(?<![a-z0-9]){re.escape(opaque_identifier_query)}(?![a-z0-9])", folded_text_blob)
        )
        title_tokens = _search_tokens(item.get("title"))
        body_tokens = _search_tokens(text_blob)
        expanded_tokens = _expanded_query_tokens(query_tokens)
        strong_tokens = _strong_query_tokens(query_tokens)
        meaningful_tokens = _meaningful_query_tokens(query_tokens)
        direct_matches = sorted(meaningful_tokens & body_tokens)
        generic_direct_matches = sorted((strong_tokens - meaningful_tokens) & body_tokens)
        weak_direct_matches = sorted((query_tokens - strong_tokens) & body_tokens)
        alias_matches = sorted((expanded_tokens - query_tokens) & body_tokens)
        alias_group_hits = 0
        for alias_group in MANUAL_NOTE_ALIAS_GROUPS:
            if query_tokens & alias_group and body_tokens & alias_group:
                alias_group_hits += 1
        high_value_tags = sorted(MANUAL_NOTE_HIGH_VALUE_TAGS & normalized_tags)
        boosted_high_value_tags = sorted(
            tag
            for tag in high_value_tags
            if MANUAL_NOTE_TAG_QUERY_GROUPS.get(tag, {tag}) & query_tokens
        )
        tag_matches = sorted(
            tag
            for tag in normalized_tags - MANUAL_NOTE_HIGH_VALUE_TAGS
            if (tag in _fold_search_text(query) or len(_tag_components(tag) & meaningful_tokens) >= 2)
        )
        title_direct_matches = sorted(meaningful_tokens & title_tokens)
        meta_tags = sorted(MANUAL_NOTE_META_TAGS & normalized_tags)
        folded_body = _fold_search_text(text_blob)
        stable_signals = [
            phrase
            for phrase in MANUAL_NOTE_STABLE_SIGNAL_PHRASES
            if _fold_search_text(phrase) in folded_body
        ]
        relevance_gate_reasons: list[str] = []
        if alias_group_hits:
            relevance_gate_reasons.append("alias_group")
        if len(title_direct_matches) >= 1:
            relevance_gate_reasons.append("title_match")
        if len(direct_matches) >= 2:
            relevance_gate_reasons.append("multiple_meaningful_matches")
        if tag_matches:
            relevance_gate_reasons.append("specific_tag_match")
        if boosted_high_value_tags and direct_matches:
            relevance_gate_reasons.append("high_value_tag_with_query_signal")
        if literal_query_match:
            relevance_gate_reasons.append("literal_query_match")
        if exact_identifier_match:
            relevance_gate_reasons.append("exact_identifier_match")
        meta_gate_passed = True
        meta_gate_reasons: list[str] = []
        meta_title_matches: list[str] = []
        if meta_tags:
            if tag_matches:
                meta_gate_reasons.append("meta_tag_match")
            meta_title_matches = sorted(set(title_direct_matches) & MANUAL_NOTE_META_QUERY_TOKENS)
            if len(meta_title_matches) >= 2:
                meta_gate_reasons.append("meta_title_match")
            if exact_identifier_match:
                meta_gate_reasons.append("exact_identifier_match")
            meta_gate_passed = bool(meta_gate_reasons)
        relevance_gate_passed = bool(relevance_gate_reasons)
        if not relevance_gate_passed or not meta_gate_passed:
            return 0.0, {}
        importance = int(item.get("importance") or 0)
        score = 8.0
        score += min(len(direct_matches), 6) * 4.0
        score += min(len(weak_direct_matches), 4) * 0.5
        score += min(len(alias_matches), 4) * 2.0
        score += alias_group_hits * 3.0
        if importance >= 4:
            score += 8.0
        score += max(0, importance - 3) * 4.0
        score += min(len(boosted_high_value_tags), 4) * 4.0
        score += min(len(tag_matches), 3) * 3.0
        score += min(len(title_direct_matches), 3) * 2.0
        if exact_identifier_match:
            score += 80.0
        if exact_title_query_match:
            score += 60.0
        elif literal_query_match:
            score += 40.0
        if title_literal_query_match:
            score += 20.0
        if body_literal_query_match:
            score += 14.0
        if tag_literal_query_match:
            score += 10.0
        if status in {"active", "promoted"}:
            score += 2.0
        score += min(len(stable_signals), 4) * 2.0
        ranking_reason = {
            "manual_note_score": round(score, 2),
            "relevance_gate_passed": relevance_gate_passed,
            "relevance_gate_reason": relevance_gate_reasons,
            "meta_gate_passed": meta_gate_passed,
            "meta_gate_reason": meta_gate_reasons,
            "meta_tags": meta_tags,
            "meta_title_matches": meta_title_matches,
            "direct_matches": direct_matches,
            "generic_direct_matches": generic_direct_matches,
            "weak_direct_matches": weak_direct_matches,
            "alias_matches": alias_matches,
            "alias_group_hits": alias_group_hits,
            "high_value_tags": high_value_tags,
            "boosted_high_value_tags": boosted_high_value_tags,
            "tag_matches": tag_matches,
            "title_direct_matches": title_direct_matches,
            "literal_query_match": literal_query_match,
            "exact_title_query_match": exact_title_query_match,
            "title_literal_query_match": title_literal_query_match,
            "body_literal_query_match": body_literal_query_match,
            "tag_literal_query_match": tag_literal_query_match,
            "exact_identifier_match": exact_identifier_match,
            "stable_signals": stable_signals,
        }
        return score, {
            "tags": list(tags),
            "retrieval_boosts": [
                "manual_note",
                f"importance={importance}",
                *(f"tag={tag}" for tag in boosted_high_value_tags),
                *(f"tag_match={tag}" for tag in tag_matches),
                *(["exact_identifier_match"] if exact_identifier_match else []),
                *(["literal_query_match"] if literal_query_match else []),
                *(f"alias={match}" for match in alias_matches[:4]),
            ],
            "ranking_reason": ranking_reason,
            "fallback_applied": fallback_applied,
        }

    def _manual_note_candidates(
        self,
        *,
        project_key: str | None,
        session_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        filters = [
            "o.source_kind = 'manual_note'",
            "o.importance >= 4",
            "LOWER(o.status) NOT IN ('low_value', 'retired', 'superseded')",
        ]
        if project_key:
            filters.append("p.project_key = ?")
            params.append(project_key)
        if session_id is not None:
            filters.append("o.session_id = ?")
            params.append(int(session_id))
        requested_limit = max(1, min(int(limit), 100))
        fetch_limit = requested_limit if session_id is not None else min(max(requested_limit * 5, requested_limit + 20), 250)
        params.append(fetch_limit)
        rows = self.conn.execute(
            f"""
            SELECT
              o.id,
              p.id AS project_id,
              p.project_key,
              p.root_path AS project_root_path,
              o.session_id,
              s.external_session_id,
              s.cwd,
              s.runtime,
              s.metadata_json,
              o.turn_id,
              o.type,
              o.title,
              o.summary,
              o.detail,
              o.importance,
              o.status,
              o.source_kind,
              o.updated_at,
              COALESCE(t.captured_at, o.updated_at) AS last_captured_turn_at
            FROM observations o
            JOIN projects p ON p.id = o.project_id
            LEFT JOIN sessions s ON s.id = o.session_id
            LEFT JOIN turns t ON t.id = o.turn_id
            WHERE {" AND ".join(filters)}
            ORDER BY o.importance DESC, o.updated_at DESC, o.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        items = self._enrich_observation_items(
            [dict(row) for row in rows],
            session_filter_applied=session_id is not None,
            retrieval_scope="session" if session_id is not None else "project",
        )
        return self._filter_cross_project_capture_items(
            items,
            session_filter_applied=session_id is not None,
        )[:requested_limit]

    def _merge_manual_note_search_results(
        self,
        items: list[dict[str, Any]],
        *,
        query: str,
        project_key: str | None,
        session_id: int | None,
        fallback_limit: int,
    ) -> list[dict[str, Any]]:
        merged: dict[int, dict[str, Any]] = {}
        original_order: dict[int, int] = {}
        for index, item in enumerate(items):
            item_id = int(item["id"])
            original_order[item_id] = index
            score, metadata = self._manual_note_retrieval_score(
                item,
                query=query,
                fallback_applied=False,
            )
            enriched = dict(item)
            if score > 0:
                enriched.update(metadata)
                enriched["_manual_note_search_score"] = score
            elif item.get("source_kind") == "manual_note":
                continue
            merged[item_id] = enriched

        candidates = self._manual_note_candidates(
            project_key=project_key,
            session_id=session_id,
            limit=fallback_limit,
        )
        for candidate in candidates:
            candidate_id = int(candidate["id"])
            score, metadata = self._manual_note_retrieval_score(
                candidate,
                query=query,
                fallback_applied=candidate_id not in merged,
            )
            if score <= 0:
                continue
            existing = merged.get(candidate_id)
            if existing is not None and float(existing.get("_manual_note_search_score") or 0.0) >= score:
                continue
            enriched = dict(candidate)
            enriched.update(metadata)
            enriched["_manual_note_search_score"] = score
            merged[candidate_id] = enriched
            original_order.setdefault(candidate_id, len(original_order))

        def sort_key(item: dict[str, Any]) -> tuple[float, int, float, int]:
            rank_value = item.get("rank")
            rank = float(rank_value) if rank_value is not None else 0.0
            return (
                -float(item.get("_manual_note_search_score") or 0.0),
                RETRIEVAL_TYPE_PRIORITY.get(str(item.get("type") or ""), 50),
                rank,
                original_order.get(int(item["id"]), 10_000),
            )

        output = sorted(merged.values(), key=sort_key)
        for item in output:
            item.pop("_manual_note_search_score", None)
        return output

    def search_observations(
        self,
        query: str,
        project_key: str | None = None,
        limit: int = 10,
        *,
        session_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if project_key and session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        requested_limit = max(1, min(int(limit), 50))
        fetch_limit = min(max(requested_limit * 5, requested_limit + 20), 250)
        if not query.strip():
            return self.recent_observations(project_key=project_key, limit=requested_limit, session_id=session_id)
        params: list[Any] = [query]
        where = ""
        type_priority_sql = _type_priority_case("o.type")
        filters: list[str] = []
        if project_key:
            filters.append("p.project_key = ?")
            params.append(project_key)
        if session_id is not None:
            filters.append("o.session_id = ?")
            params.append(int(session_id))
        if filters:
            where = "AND " + " AND ".join(filters)
        params.append(fetch_limit)
        try:
            rows = self.conn.execute(
                f"""
                SELECT
                  o.id,
                  p.id AS project_id,
                  p.project_key,
                  p.root_path AS project_root_path,
                  o.session_id,
                  s.external_session_id,
                  s.cwd,
                  s.runtime,
                  s.metadata_json,
                  o.turn_id,
                  o.type,
                  o.title,
                  o.summary,
                  o.detail,
                  o.importance,
                  o.status,
                  o.source_kind,
                  o.updated_at,
                  COALESCE(t.captured_at, o.updated_at) AS last_captured_turn_at,
                  bm25(observations_fts) AS rank
                FROM observations_fts
                JOIN observations o ON o.id = observations_fts.rowid
                JOIN projects p ON p.id = o.project_id
                LEFT JOIN sessions s ON s.id = o.session_id
                LEFT JOIN turns t ON t.id = o.turn_id
                WHERE observations_fts MATCH ? {where}
                ORDER BY {type_priority_sql}, rank, o.updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        except sqlite3.OperationalError:
            like_query = f"%{query}%"
            params = [like_query, like_query, like_query]
            where = ""
            filters = []
            if project_key:
                filters.append("p.project_key = ?")
                params.append(project_key)
            if session_id is not None:
                filters.append("o.session_id = ?")
                params.append(int(session_id))
            if filters:
                where = "AND " + " AND ".join(filters)
            params.append(fetch_limit)
            rows = self.conn.execute(
                f"""
                SELECT
                  o.id,
                  p.id AS project_id,
                  p.project_key,
                  p.root_path AS project_root_path,
                  o.session_id,
                  s.external_session_id,
                  s.cwd,
                  s.runtime,
                  s.metadata_json,
                  o.turn_id,
                  o.type,
                  o.title,
                  o.summary,
                  o.detail,
                  o.importance,
                  o.status,
                  o.source_kind,
                  o.updated_at,
                  COALESCE(t.captured_at, o.updated_at) AS last_captured_turn_at
                FROM observations o
                JOIN projects p ON p.id = o.project_id
                LEFT JOIN sessions s ON s.id = o.session_id
                LEFT JOIN turns t ON t.id = o.turn_id
                WHERE (o.title LIKE ? OR o.summary LIKE ? OR o.detail LIKE ?) {where}
                ORDER BY {type_priority_sql}, o.updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        items = self._enrich_observation_items(
            [dict(row) for row in rows],
            session_filter_applied=session_id is not None,
            retrieval_scope="session" if session_id is not None else "project",
        )
        items = self._filter_cross_project_capture_items(
            items,
            session_filter_applied=session_id is not None,
        )
        items = self._merge_manual_note_search_results(
            items,
            query=query,
            project_key=project_key,
            session_id=session_id,
            fallback_limit=fetch_limit,
        )
        items = self._filter_cross_project_capture_items(
            items,
            session_filter_applied=session_id is not None,
        )
        if project_key:
            excluded = self._effective_governance(project_key)["retrieval_excluded_keys"]
            items = filter_items_by_policy(items, excluded_keys=excluded)
        items, _dedupe_stats = dedupe_retrieval_items(items)
        return items[:requested_limit]

    def get_observation(self, observation_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT o.*, p.project_key
            FROM observations o
            JOIN projects p ON p.id = o.project_id
            WHERE o.id = ?
            """,
            (observation_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        files = self.conn.execute(
            "SELECT file_path FROM observation_files WHERE observation_id = ? ORDER BY file_path",
            (observation_id,),
        ).fetchall()
        result["files"] = [f["file_path"] for f in files]
        return result

    def get_provenance(self, *, memory_id: int, memory_kind: str = "observation") -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT
              mp.*,
              p.project_key,
              p.name AS project_name,
              s.runtime,
              s.external_session_id,
              t.external_turn_id,
              t.captured_at,
              t.input_messages_json,
              t.assistant_message,
              t.raw_payload_json,
              o.type AS observation_type,
              o.title AS observation_title,
              o.summary AS observation_summary,
              o.detail AS observation_detail,
              o.updated_at AS observation_updated_at
            FROM memory_provenance mp
            JOIN projects p ON p.id = mp.project_id
            LEFT JOIN sessions s ON s.id = mp.session_id
            LEFT JOIN turns t ON t.id = mp.turn_id
            LEFT JOIN observations o ON o.id = mp.observation_id
            WHERE mp.memory_kind = ? AND mp.memory_id = ?
            """,
            (memory_kind, memory_id),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["source_span"] = self._load_json(result.pop("source_span_json", None), {})
        raw_turn = {
            "turn_id": result.get("turn_id"),
            "external_turn_id": result.get("external_turn_id"),
            "captured_at": result.get("captured_at"),
            "turn_hash": result.get("turn_hash"),
            "input_messages": self._load_json(result.get("input_messages_json"), []),
            "assistant_message": result.get("assistant_message"),
            "raw_payload": self._load_json(result.get("raw_payload_json"), {}),
        }
        result["source_turn"] = raw_turn if result.get("turn_id") else None
        result["source_session"] = (
            {
                "session_id": result.get("session_id"),
                "external_session_id": result.get("external_session_id"),
                "runtime": result.get("runtime"),
                "cwd": result.get("cwd"),
                "model_name": result.get("model_name"),
            }
            if result.get("session_id")
            else None
        )
        result["source_observation"] = (
            {
                "observation_id": result.get("observation_id"),
                "type": result.get("observation_type"),
                "title": result.get("observation_title"),
                "summary": result.get("observation_summary"),
                "detail": result.get("observation_detail"),
                "updated_at": result.get("observation_updated_at"),
            }
            if result.get("observation_id")
            else None
        )
        return result

    def list_sessions(
        self,
        project_key: str,
        limit: int = 50,
        *,
        query: str | None = None,
        sub_scope_hint: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        filtering = bool((query and query.strip()) or (sub_scope_hint and sub_scope_hint.strip()))
        fetch_limit = min(max(limit * 5, limit + 20), 250) if filtering else limit
        rows = self.conn.execute(
            """
            SELECT
              s.id,
              s.project_id,
              s.runtime,
              s.external_session_id,
              s.started_at,
              s.ended_at,
              s.cwd,
              p.root_path AS project_root_path,
              s.metadata_json,
              (
                SELECT t_first.input_messages_json
                FROM turns t_first
                WHERE t_first.session_id = s.id
                ORDER BY t_first.captured_at ASC, t_first.id ASC
                LIMIT 1
              ) AS first_input_messages_json,
              COUNT(DISTINCT t.id) AS turn_count,
              COUNT(DISTINCT o.id) AS observation_count,
              COALESCE(MAX(t.captured_at), s.started_at) AS last_turn_at
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
            LEFT JOIN turns t ON t.session_id = s.id
            LEFT JOIN observations o ON o.session_id = s.id
            WHERE p.project_key = ?
            GROUP BY s.id
            ORDER BY COALESCE(MAX(t.captured_at), s.started_at) DESC, s.id DESC
            LIMIT ?
            """,
            (project_key, fetch_limit),
        ).fetchall()
        sessions = [self._session_preview(dict(row)) for row in rows]
        if filtering:
            sessions = [
                item
                for item in sessions
                if session_matches_query(item, query=query, sub_scope_hint=sub_scope_hint)
            ]
        return sessions[:limit]

    def _scope_sessions_for_project(self, project_key: str, limit: int = 100) -> list[dict[str, Any]]:
        return [
            item
            for item in self.list_sessions(project_key, limit=limit)
            if item.get("project_root_match") is not False
        ]

    def list_recent_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
              s.id,
              s.project_id,
              s.runtime,
              s.external_session_id,
              s.started_at,
              s.ended_at,
              s.cwd,
              s.metadata_json,
              p.project_key,
              p.name AS project_name,
              p.root_path,
              (
                SELECT t_first.input_messages_json
                FROM turns t_first
                WHERE t_first.session_id = s.id
                ORDER BY t_first.captured_at ASC, t_first.id ASC
                LIMIT 1
              ) AS first_input_messages_json,
              COUNT(DISTINCT t.id) AS turn_count,
              COUNT(DISTINCT o.id) AS observation_count,
              COALESCE(MAX(t.captured_at), s.started_at) AS last_turn_at
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
            LEFT JOIN turns t ON t.session_id = s.id
            LEFT JOIN observations o ON o.session_id = s.id
            GROUP BY s.id
            ORDER BY COALESCE(MAX(t.captured_at), s.started_at) DESC, s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT
              s.*,
              p.project_key,
              p.name AS project_name,
              p.root_path,
              (
                SELECT t_first.input_messages_json
                FROM turns t_first
                WHERE t_first.session_id = s.id
                ORDER BY t_first.captured_at ASC, t_first.id ASC
                LIMIT 1
              ) AS first_input_messages_json,
              (SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id) AS turn_count,
              (SELECT COUNT(*) FROM observations o WHERE o.session_id = s.id) AS observation_count,
              COALESCE((SELECT MAX(t.captured_at) FROM turns t WHERE t.session_id = s.id), s.started_at) AS last_turn_at
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()
        return self._session_preview(dict(row)) if row is not None else None

    def _sessions_by_ids(self, session_ids: set[int]) -> list[dict[str, Any]]:
        if not session_ids:
            return []
        placeholders = ",".join("?" for _ in session_ids)
        rows = self.conn.execute(
            f"""
            SELECT
              s.*,
              p.project_key,
              p.name AS project_name,
              p.root_path AS project_root_path,
              (
                SELECT t_first.input_messages_json
                FROM turns t_first
                WHERE t_first.session_id = s.id
                ORDER BY t_first.captured_at ASC, t_first.id ASC
                LIMIT 1
              ) AS first_input_messages_json,
              (SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id) AS turn_count,
              (SELECT COUNT(*) FROM observations o WHERE o.session_id = s.id) AS observation_count,
              COALESCE((SELECT MAX(t.captured_at) FROM turns t WHERE t.session_id = s.id), s.started_at) AS last_turn_at
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
            WHERE s.id IN ({placeholders})
            """,
            [int(item) for item in sorted(session_ids)],
        ).fetchall()
        sessions = [self._session_preview(dict(row)) for row in rows]
        return sorted(sessions, key=lambda item: (str(item.get("last_turn_at") or ""), int(item.get("id") or 0)), reverse=True)

    @staticmethod
    def _source_session_ids(source_items: list[dict[str, Any]], source_turns: list[dict[str, Any]]) -> set[int]:
        ids: set[int] = set()
        for item in [*source_items, *source_turns]:
            raw_session_id = item.get("session_id")
            if raw_session_id is None:
                continue
            try:
                ids.add(int(raw_session_id))
            except (TypeError, ValueError):
                continue
        return ids

    @classmethod
    def _latest_captured_at(
        cls,
        source_items: list[dict[str, Any]],
        source_turns: list[dict[str, Any]],
        source_sessions: list[dict[str, Any]],
    ) -> str | None:
        candidates: list[tuple[datetime, str]] = []
        for item in source_items:
            raw = item.get("last_captured_turn_at") or item.get("updated_at")
            parsed = cls._parse_timestamp(str(raw) if raw else None)
            if parsed is not None and raw:
                candidates.append((parsed, str(raw)))
        for turn in source_turns:
            raw = turn.get("captured_at")
            parsed = cls._parse_timestamp(str(raw) if raw else None)
            if parsed is not None and raw:
                candidates.append((parsed, str(raw)))
        for session in source_sessions:
            raw = session.get("last_turn_at")
            parsed = cls._parse_timestamp(str(raw) if raw else None)
            if parsed is not None and raw:
                candidates.append((parsed, str(raw)))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])[1]

    @classmethod
    def _latest_operational_captured_at(
        cls,
        source_items: list[dict[str, Any]],
        source_turns: list[dict[str, Any]],
    ) -> str | None:
        candidates: list[tuple[datetime, str]] = []
        for item in source_items:
            if is_internal_prompt_noise(item_text(item)):
                continue
            raw = item.get("last_captured_turn_at") or item.get("updated_at")
            parsed = cls._parse_timestamp(str(raw) if raw else None)
            if parsed is not None and raw:
                candidates.append((parsed, str(raw)))
        for turn in source_turns:
            turn_text = " ".join(
                [
                    *[str(message or "") for message in (turn.get("input_messages") or [])],
                    str(turn.get("assistant_message") or ""),
                ]
            )
            if not turn_text.strip() or is_internal_prompt_noise(turn_text):
                continue
            raw = turn.get("captured_at")
            parsed = cls._parse_timestamp(str(raw) if raw else None)
            if parsed is not None and raw:
                candidates.append((parsed, str(raw)))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])[1]

    def _context_scope_metadata(
        self,
        project_key: str,
        *,
        session_id: int | None,
        source_items: list[dict[str, Any]],
        source_turns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        source_session_ids = self._source_session_ids(source_items, source_turns)
        if session_id is not None:
            source_session_ids.add(int(session_id))
        source_sessions = self._sessions_by_ids(source_session_ids)
        if not source_sessions and session_id is not None:
            session = self.get_session(session_id)
            if session is not None:
                source_sessions = [session]
        if session_id is None:
            # Project-wide packs must describe the persisted project scope, not
            # only the sessions that happened to survive ranking/budget.
            project_sessions = self._scope_sessions_for_project(project_key, limit=100)
            if project_sessions:
                source_sessions = project_sessions

        source_texts = [item_text(item) for item in source_items]
        for turn in source_turns:
            source_texts.extend(str(message or "") for message in (turn.get("input_messages") or []))
            source_texts.append(str(turn.get("assistant_message") or ""))
        inferred = infer_sub_scope(None, source_texts)
        narrowing_candidates: set[str] = set()

        def add_narrowing_candidate(value: Any) -> None:
            candidate = _recommended_narrowing_candidate(value)
            if candidate:
                narrowing_candidates.add(candidate)

        for item in source_sessions:
            add_narrowing_candidate(item.get("cwd"))
            add_narrowing_candidate(item.get("inferred_sub_scope"))
            for candidate in item.get("sub_scope_candidates") or []:
                add_narrowing_candidate(candidate)
        for candidate in inferred.get("sub_scope_candidates") or []:
            add_narrowing_candidate(candidate)
        sub_scopes = {
            str(item.get("inferred_sub_scope"))
            for item in source_sessions
            if item.get("inferred_sub_scope")
        }
        if inferred.get("inferred_sub_scope"):
            sub_scopes.add(str(inferred["inferred_sub_scope"]))
        source_sub_scopes = sorted(sub_scopes)
        candidate_lanes = _scope_lane_inventory(source_sessions, limit=8)
        multiple_sessions_detected = session_id is None and len(source_sessions) > 1
        multiple_lanes_detected = len(candidate_lanes) > 1
        broad_scope_detected = session_id is None and (
            multiple_sessions_detected
            or multiple_lanes_detected
            or len(source_sub_scopes) > 1
        )
        warning_needed = broad_scope_detected
        recommended_narrowing = None
        if warning_needed:
            candidate_sub_scopes = sorted(narrowing_candidates)[:8]
            query_target = "<target sub-scope>"
            recommended_narrowing = {
                "reason": "project-wide pack spans multiple persisted sessions or inferred sub-scopes",
                "candidate_sub_scopes": candidate_sub_scopes,
                "next_steps": [
                    {
                        "tool": "mem_session_list",
                        "arguments": {
                            "project_key": project_key,
                            "query": query_target,
                        },
                        "then": "mem_context_pack(project_key, session_id=<chosen_session_id>)",
                    },
                    {
                        "tool": "mem_search",
                        "arguments": {
                            "project_key": project_key,
                            "query": f"{query_target} estado actual decisiones pendientes",
                        },
                    },
                ],
                "confidence": "medium" if candidate_sub_scopes else "low",
            }
        scope_warning = (
            {
                "code": "multi_session_project_scope",
                "severity": "warn",
                "message": "Project-wide context includes multiple persisted sessions or inferred sub-scopes.",
                "recommendation": "Use mem_session_list(project_key) and retry with session_id to narrow broad project scopes.",
            }
            if warning_needed
            else None
        )
        last_captured_turn_at = self._latest_captured_at(source_items, source_turns, source_sessions)
        last_operational_capture_at = self._latest_operational_captured_at(source_items, source_turns)
        return {
            "project_key": project_key,
            "scope_mode": "session" if session_id is not None else "project",
            "session_filter_applied": session_id is not None,
            "source_session_count": len(source_sessions),
            "source_sessions": source_sessions[:6],
            "source_sessions_truncated": len(source_sessions) > 6,
            "source_sub_scope_count": len(source_sub_scopes),
            "source_sub_scopes": source_sub_scopes[:8],
            "candidate_lanes": candidate_lanes,
            "candidate_sub_scopes": [str(item["inferred_sub_scope"]) for item in candidate_lanes],
            "multiple_sessions_detected": multiple_sessions_detected,
            "multiple_lanes_detected": multiple_lanes_detected,
            "broad_scope_detected": broad_scope_detected,
            "do_not_fetch_project_wide_pack": broad_scope_detected,
            "scope_warning": scope_warning,
            "recommended_narrowing": recommended_narrowing,
            "active_objective_uncertain": bool(scope_warning),
            "active_objective_suppressed": bool(scope_warning),
            "active_objective_suppression_reason": (
                "project-wide pack spans multiple persisted sessions or inferred sub-scopes"
                if scope_warning
                else None
            ),
            "last_captured_turn_at": last_captured_turn_at,
            "last_operational_capture_at": last_operational_capture_at,
            "memory_age_seconds": self._memory_age_seconds(last_captured_turn_at),
            "operational_memory_age_seconds": self._memory_age_seconds(last_operational_capture_at),
            "memory_freshness": "unknown" if last_captured_turn_at is None else "persisted",
            "live_turn_awareness": False,
        }

    @staticmethod
    def _scope_notice_lines(scope_meta: dict[str, Any]) -> list[str]:
        if not scope_meta.get("session_filter_applied") and not scope_meta.get("scope_warning"):
            return []
        session_count = int(scope_meta.get("source_session_count") or 0)
        sub_scope_count = int(scope_meta.get("source_sub_scope_count") or 0)
        if scope_meta.get("session_filter_applied"):
            source_sessions = scope_meta.get("source_sessions") or []
            source = source_sessions[0] if source_sessions else {}
            external_session_id = source.get("external_session_id") or source.get("session_id") or "unknown"
            lines = [
                "Session scope: session-scoped; "
                f"session_filter=applied; source_sessions={session_count}; "
                f"external_session_id={external_session_id}."
            ]
        else:
            lines = [
                "Session scope: project-wide; "
                f"session_filter=not_applied; source_sessions={session_count}; sub_scopes={sub_scope_count}."
            ]
        if scope_meta.get("scope_warning"):
            lines.append(
                "Scope warning: mixed persisted sessions/sub-scopes. "
                "Use `mem_session_list` + `session_id`."
            )
            lines.append(
                "No active objective selected: this project-wide pack is advisory until narrowed."
            )
        recommended_narrowing = scope_meta.get("recommended_narrowing")
        if isinstance(recommended_narrowing, dict):
            query_target = "<target sub-scope>"
            lines.append(
                "Suggested narrowing: choose a target from candidate_sub_scopes, then call "
                f'mem_session_list(project_key, query="{query_target}") before treating this '
                "project-wide pack as active context."
            )
        last_operational = scope_meta.get("last_operational_capture_at")
        last_captured = scope_meta.get("last_captured_turn_at")
        if last_operational:
            if last_captured and last_captured != last_operational:
                lines.append(
                    f"Last operational capture: `{last_operational}` "
                    f"(last captured turn: `{last_captured}`). "
                    "Persisted; not live current-turn awareness."
                )
            else:
                lines.append(
                    f"Last operational capture: `{last_operational}`. "
                    "Persisted; not live current-turn awareness."
                )
        elif last_captured:
            lines.append(
                f"Last captured turn: `{last_captured}`. "
                "Persisted; not live current-turn awareness."
            )
        return lines

    def list_turns(self, session_id: int, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
              t.id,
              t.session_id,
              t.external_turn_id,
              t.captured_at,
              t.assistant_message,
              SUBSTR(REPLACE(t.assistant_message, CHAR(10), ' '), 1, 180) AS assistant_preview,
              COUNT(o.id) AS observation_count
            FROM turns t
            LEFT JOIN observations o ON o.turn_id = t.id
            WHERE t.session_id = ?
            GROUP BY t.id
            ORDER BY t.captured_at DESC, t.id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_turn(self, turn_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT
              t.*,
              s.external_session_id,
              s.cwd,
              p.project_key,
              p.name AS project_name
            FROM turns t
            JOIN sessions s ON s.id = t.session_id
            JOIN projects p ON p.id = s.project_id
            WHERE t.id = ?
            """,
            (turn_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        observations = self.conn.execute(
            """
            SELECT id, project_id, session_id, turn_id, type, title, summary, status, updated_at
            FROM observations
            WHERE turn_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (turn_id,),
        ).fetchall()
        result["observations"] = [dict(obs) for obs in observations]
        return result

    def recent_turn_context(
        self,
        project_key: str,
        limit: int = 8,
        *,
        session_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        session_filter = ""
        params: list[Any] = [project_key]
        if session_id is not None:
            session_filter = "AND s.id = ?"
            params.append(int(session_id))
        fetch_limit = limit if session_id is not None else min(max(limit * 5, limit + 20), 250)
        params.append(fetch_limit)
        rows = self.conn.execute(
            f"""
            SELECT
              t.id,
              p.root_path AS project_root_path,
              s.id AS session_id,
              s.runtime,
              s.external_session_id,
              s.cwd,
              s.metadata_json,
              t.input_messages_json,
              t.assistant_message,
              t.captured_at
            FROM turns t
            JOIN sessions s ON s.id = t.session_id
            JOIN projects p ON p.id = s.project_id
            WHERE p.project_key = ? {session_filter}
            ORDER BY t.captured_at DESC, t.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            metadata = self._load_json(payload.pop("metadata_json", None), {})
            if not isinstance(metadata, dict):
                metadata = {}
            metadata_project_root_path = metadata.get("project_root_path")
            payload["project_root_path"] = metadata_project_root_path or payload.get("project_root_path")
            payload["project_root_match"] = (
                _path_is_within_root(payload.get("cwd"), payload.get("project_root_path"))
                if metadata_project_root_path
                else True
            )
            if payload["project_root_match"] is False:
                source = str(metadata.get("project_resolution_source") or "")
                payload["cross_project_capture_warning"] = (
                    "mentioned_path_capture_cwd_outside_project_root"
                    if source.startswith("mentioned_path")
                    else "session_cwd_outside_project_root"
                )
            if session_id is None and payload.get("project_root_match") is False:
                continue
            try:
                payload["input_messages"] = json.loads(payload.get("input_messages_json") or "[]")
            except json.JSONDecodeError:
                payload["input_messages"] = []
            items.append(payload)
        return items[:limit]

    def _project_row(self, project_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT id, project_key, name, root_path, updated_at FROM projects WHERE project_key = ?",
            (project_key,),
        ).fetchone()

    def validate_policy(self, policy_kind: str, rule: dict[str, Any] | None) -> dict[str, Any]:
        result = validate_policy_definition(policy_kind, rule)
        return {
            "policy_kind": policy_kind,
            "valid": result["valid"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "normalized_rule": result["normalized_rule"],
        }

    def list_policies(self, project_key: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT mp.*, p.project_key
            FROM memory_policies mp
            JOIN projects p ON p.id = mp.project_id
            WHERE p.project_key = ?
            ORDER BY mp.created_at DESC, mp.id DESC
            """,
            (project_key,),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item.get("enabled"))
            item["rule"] = self._load_json(item.pop("rule_json", None), {})
            items.append(item)
        return items

    def add_policy(
        self,
        project_key: str,
        policy_kind: str,
        rule: dict[str, Any] | None,
        *,
        enabled: bool = True,
    ) -> dict[str, Any]:
        project = self._project_row(project_key)
        if project is None:
            raise ValueError("Project not found")
        validation = self.validate_policy(policy_kind, rule)
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO memory_policies(project_id, policy_kind, rule_json, enabled, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(project["id"]),
                    policy_kind,
                    self._json(validation["normalized_rule"]),
                    1 if enabled else 0,
                    self._now(),
                ),
            )
            policy_id = int(cur.lastrowid)
        rows = [item for item in self.list_policies(project_key) if int(item["id"]) == policy_id]
        assert rows
        return rows[0]

    def remove_policy(self, project_key: str, policy_id: int) -> dict[str, Any]:
        project = self._project_row(project_key)
        if project is None:
            raise ValueError("Project not found")
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM memory_policies WHERE id = ? AND project_id = ?",
                (policy_id, int(project["id"])),
            )
        return {"project_key": project_key, "policy_id": policy_id, "removed": cur.rowcount > 0}

    def validate_inheritance(self, mode: str, selector: dict[str, Any] | None) -> dict[str, Any]:
        result = validate_inheritance_definition(mode, selector)
        return {
            "mode": mode,
            "valid": result["valid"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "normalized_selector": result["normalized_selector"],
        }

    def list_inheritances(self, project_key: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
              i.*,
              tp.project_key AS target_project_key,
              sp.project_key AS source_project_key
            FROM project_inheritances i
            JOIN projects tp ON tp.id = i.target_project_id
            JOIN projects sp ON sp.id = i.source_project_id
            WHERE tp.project_key = ?
            ORDER BY i.created_at DESC, i.id DESC
            """,
            (project_key,),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item.get("enabled"))
            item["selector"] = self._load_json(item.pop("selector_json", None), {})
            items.append(item)
        return items

    def add_inheritance(
        self,
        target_project_key: str,
        source_project_key: str,
        mode: str,
        selector: dict[str, Any] | None = None,
        *,
        enabled: bool = True,
    ) -> dict[str, Any]:
        target = self._project_row(target_project_key)
        source = self._project_row(source_project_key)
        if target is None or source is None:
            raise ValueError("Source or target project not found")
        validation = self.validate_inheritance(mode, selector)
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO project_inheritances(
                  target_project_id, source_project_id, mode, selector_json, enabled, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(target["id"]),
                    int(source["id"]),
                    mode,
                    self._json(validation["normalized_selector"]),
                    1 if enabled else 0,
                    self._now(),
                ),
            )
            inheritance_id = int(cur.lastrowid)
        rows = [item for item in self.list_inheritances(target_project_key) if int(item["id"]) == inheritance_id]
        assert rows
        return rows[0]

    def remove_inheritance(self, project_key: str, inheritance_id: int) -> dict[str, Any]:
        target = self._project_row(project_key)
        if target is None:
            raise ValueError("Project not found")
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM project_inheritances WHERE id = ? AND target_project_id = ?",
                (inheritance_id, int(target["id"])),
            )
        return {"project_key": project_key, "inheritance_id": inheritance_id, "removed": cur.rowcount > 0}

    def list_repairs(self, project_key: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT r.*
            FROM repair_events r
            JOIN projects p ON p.id = r.project_id
            WHERE p.project_key = ?
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ?
            """,
            (project_key, limit),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["approved"] = bool(item.get("approved"))
            item["before_ref"] = self._load_json(item.pop("before_ref_json", None), {})
            item["after_ref"] = self._load_json(item.pop("after_ref_json", None), {})
            items.append(item)
        return items

    @staticmethod
    def _policy_item_from_observation(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "type": item.get("type"),
            "title": item.get("title"),
            "summary": item.get("summary") or item.get("title"),
            # Policy matching intentionally avoids raw turn detail here.
            # Observation detail often contains the full captured turn, which
            # makes text-based policies overmatch unrelated sibling items.
            "detail": item.get("summary") or item.get("title"),
            "status": item.get("status"),
            "updated_at": item.get("updated_at"),
            "effective_tags": item.get("effective_tags") or [],
            "memory_kind": "observation",
        }

    @staticmethod
    def _policy_item_from_decision(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "type": "decision",
            "title": item.get("title"),
            "summary": item.get("decision_text") or item.get("title"),
            "detail": item.get("decision_text"),
            "decision_text": item.get("decision_text"),
            "status": item.get("status"),
            "updated_at": item.get("updated_at"),
            "memory_kind": "decision",
        }

    def _enabled_policy_rows(self, project_key: str) -> list[dict[str, Any]]:
        return [item for item in self.list_policies(project_key) if item.get("enabled")]

    def _enabled_inheritance_rows(self, project_key: str) -> list[dict[str, Any]]:
        return [item for item in self.list_inheritances(project_key) if item.get("enabled")]

    def _approved_repairs(self, project_key: str) -> list[dict[str, Any]]:
        return [item for item in self.list_repairs(project_key, limit=50) if item.get("approved")]

    def _inherited_rule_rows(self, project_key: str) -> list[dict[str, Any]]:
        inherited: list[dict[str, Any]] = []
        for item in self._enabled_inheritance_rows(project_key):
            if item.get("mode") not in {"rules_only", "combined"}:
                continue
            source_key = str(item.get("source_project_key"))
            for policy in self._enabled_policy_rows(source_key):
                inherited.append(
                    {
                        **policy,
                        "inherited_from_project_key": source_key,
                        "origin": "inherited_rule",
                    }
                )
        return inherited

    def _inherited_decisions(self, project_key: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for inheritance in self._enabled_inheritance_rows(project_key):
            if inheritance.get("mode") not in {"stable_decisions", "combined"}:
                continue
            source_key = str(inheritance.get("source_project_key"))
            selector = inheritance.get("selector") or {}
            limit = int(selector.get("limit") or 8)
            for decision in self.recent_decisions(source_key, limit=limit):
                policy_item = self._policy_item_from_decision(decision)
                if not selector_matches(policy_item, selector):
                    continue
                inherited = dict(decision)
                inherited["id"] = f"inh-decision:{source_key}:{decision['id']}"
                inherited["title"] = f"{decision['title']} (inherited from {source_key})"
                inherited["decision_text"] = f"{decision['decision_text']} (inherited from {source_key})"
                inherited["inherited_from_project_key"] = source_key
                inherited["memory_kind"] = "decision"
                items.append(inherited)
        return items

    def _inherited_observations(self, project_key: str) -> list[dict[str, Any]]:
        inherited_items: list[dict[str, Any]] = []
        for inheritance in self._enabled_inheritance_rows(project_key):
            if inheritance.get("mode") not in {"marked_inheritable", "combined"}:
                continue
            source_key = str(inheritance.get("source_project_key"))
            selector = inheritance.get("selector") or {}
            source_policies = self._enabled_policy_rows(source_key)
            source_observations = self._operational_observations(source_key, limit=240)
            source_policy_items = [self._policy_item_from_observation(item) for item in source_observations]
            source_effects = evaluate_policy_effects(
                source_policy_items,
                source_policies,
                self._approved_repairs(source_key),
            )
            source_tags = source_effects["tag_map"]
            excluded = set(source_effects["retrieval_excluded_keys"])
            added = 0
            for item in source_observations:
                policy_item = self._policy_item_from_observation(item)
                key = f"observation:{item['id']}"
                if key in excluded:
                    continue
                tags = set(source_tags.get(key) or [])
                if not selector_matches(policy_item, selector, tags=tags):
                    continue
                inherited = dict(item)
                inherited["id"] = f"inh-observation:{source_key}:{item['id']}"
                inherited["title"] = f"{item['title']} (inherited from {source_key})"
                inherited["summary"] = f"{item['summary']} (inherited from {source_key})"
                inherited["detail"] = f"{item.get('detail') or item.get('summary') or item.get('title')} (inherited from {source_key})"
                inherited["effective_tags"] = sorted(tags)
                inherited["inherited_from_project_key"] = source_key
                inherited["memory_kind"] = "observation"
                inherited_items.append(inherited)
                added += 1
                if added >= int(selector.get("limit") or 8):
                    break
        return inherited_items

    def _repair_proposals_from_health(
        self,
        project_key: str,
        *,
        record_if_missing: bool = True,
    ) -> list[dict[str, Any]]:
        report = self.latest_health_report(project_key)
        if report is None and record_if_missing:
            self.health_report(project_key, record=True)
            report = self.latest_health_report(project_key)
        if report is None:
            return []
        operational_observations = self._operational_observations(project_key, limit=240)
        policies = self._enabled_policy_rows(project_key)
        effects = evaluate_policy_effects(
            [self._policy_item_from_observation(item) for item in operational_observations],
            policies,
            self._approved_repairs(project_key),
        )
        protected = set(effects["never_archive_keys"])
        proposals: list[dict[str, Any]] = []
        for duplicate in report.get("duplicates") or []:
            ids = [int(item_id) for item_id in duplicate.get("observation_ids") or []]
            if len(ids) <= 1:
                continue
            candidate_ids = [item_id for item_id in ids[1:] if f"observation:{item_id}" not in protected]
            if candidate_ids:
                proposals.append(
                    {
                        "repair_kind": "archive_duplicate_observations",
                        "supported_apply": True,
                        "observation_ids": candidate_ids,
                        "reason": duplicate.get("latest_summary") or duplicate.get("normalized_text"),
                        "health_report_id": report.get("id"),
                    }
                )
        stale_ids: list[int] = []
        stale_summaries = {str(item.get("summary") or "") for item in report.get("stale_items") or []}
        for item in operational_observations:
            if str(item.get("summary") or "") in stale_summaries and f"observation:{item['id']}" not in protected:
                stale_ids.append(int(item["id"]))
        if stale_ids:
            proposals.append(
                {
                    "repair_kind": "archive_stale_open_items",
                    "supported_apply": True,
                    "observation_ids": sorted(set(stale_ids)),
                    "reason": "stale_open_items",
                    "health_report_id": report.get("id"),
                }
            )
        if report.get("contradictions"):
            proposals.append(
                {
                    "repair_kind": "review_contradictions",
                    "supported_apply": False,
                    "observation_ids": [],
                    "reason": "manual_review_required",
                    "health_report_id": report.get("id"),
                }
            )
        if report.get("dod_missing_count"):
            proposals.append(
                {
                    "repair_kind": "review_dod_gaps",
                    "supported_apply": False,
                    "observation_ids": [],
                    "reason": "manual_review_required",
                    "health_report_id": report.get("id"),
                }
            )
        return proposals

    def apply_repair(self, project_key: str, repair_kind: str, health_report_id: int | None = None) -> dict[str, Any]:
        project = self._project_row(project_key)
        if project is None:
            raise ValueError("Project not found")
        proposals = self._repair_proposals_from_health(project_key)
        proposal = next(
            (
                item
                for item in proposals
                if item["repair_kind"] == repair_kind
                and (health_report_id is None or int(item.get("health_report_id") or 0) == health_report_id)
            ),
            None,
        )
        if proposal is None:
            raise ValueError("Repair proposal not found")
        if not proposal.get("supported_apply"):
            raise ValueError("This repair proposal requires manual review and cannot be auto-applied")
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO repair_events(
                  project_id, health_report_id, repair_kind, before_ref_json, after_ref_json, approved, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(project["id"]),
                    int(proposal.get("health_report_id") or 0) or None,
                    repair_kind,
                    self._json(
                        {
                            "proposal_reason": proposal.get("reason"),
                            "health_report_id": proposal.get("health_report_id"),
                        }
                    ),
                    self._json({"exclude_observation_ids": proposal.get("observation_ids") or []}),
                    1,
                    self._now(),
                ),
            )
            repair_id = int(cur.lastrowid)
        latest_turn = self._latest_turn_source(int(project["id"]))
        self.record_provenance(
            memory_kind="repair_event",
            memory_id=repair_id,
            project_id=int(project["id"]),
            session_id=int(latest_turn["session_id"]) if latest_turn else None,
            turn_id=int(latest_turn["turn_id"]) if latest_turn else None,
            observation_id=None,
            turn_hash=str(latest_turn["content_hash"]) if latest_turn and latest_turn.get("content_hash") else None,
            model_name=str(latest_turn["model_name"]) if latest_turn and latest_turn.get("model_name") else None,
            cwd=str(latest_turn["cwd"]) if latest_turn and latest_turn.get("cwd") else None,
            source_span={
                "repair_kind": repair_kind,
                "exclude_observation_ids": proposal.get("observation_ids") or [],
            },
        )
        rows = [item for item in self.list_repairs(project_key) if int(item["id"]) == repair_id]
        assert rows
        return rows[0]

    def _effective_governance(self, project_key: str, *, session_id: int | None = None) -> dict[str, Any]:
        if session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        local_policies = self._enabled_policy_rows(project_key)
        inherited_policies = self._inherited_rule_rows(project_key)
        effective_policies = local_policies + inherited_policies
        local_observations = self._operational_observations(project_key, limit=480, session_id=session_id)
        local_decisions = self.recent_decisions(project_key, limit=20, session_id=session_id)
        inherited_observations = [] if session_id is not None else self._inherited_observations(project_key)
        inherited_decisions = [] if session_id is not None else self._inherited_decisions(project_key)
        effects = evaluate_policy_effects(
            [self._policy_item_from_observation(item) for item in local_observations]
            + [self._policy_item_from_observation(item) for item in inherited_observations]
            + [self._policy_item_from_decision(item) for item in local_decisions]
            + [self._policy_item_from_decision(item) for item in inherited_decisions],
            effective_policies,
            self._approved_repairs(project_key),
        )
        retrieval_excluded = set(effects["retrieval_excluded_keys"])
        pack_excluded = set(effects["pack_excluded_keys"])
        keep_priority = set(effects["keep_priority_keys"])
        effective_local_observations = []
        for item in local_observations:
            key = f"observation:{item['id']}"
            if key in retrieval_excluded:
                continue
            enriched = dict(item)
            enriched["effective_tags"] = effects["tag_map"].get(key) or []
            effective_local_observations.append(enriched)
        effective_local_observations = sort_items_for_priority(
            effective_local_observations,
            priority_keys=keep_priority,
        )
        effective_inherited_observations = filter_items_by_policy(
            [dict(item, memory_kind="observation") for item in inherited_observations],
            excluded_keys=retrieval_excluded,
        )
        effective_inherited_observations = sort_items_for_priority(
            effective_inherited_observations,
            priority_keys=keep_priority,
        )
        effective_decisions = sort_items_for_priority(
            filter_items_by_policy(
                [dict(item, memory_kind="decision") for item in local_decisions] + inherited_decisions,
                excluded_keys=retrieval_excluded,
            ),
            priority_keys=keep_priority,
        )
        return {
            "local_policies": local_policies,
            "effective_policies": effective_policies,
            "inheritances": self._enabled_inheritance_rows(project_key),
            "repairs": self.list_repairs(project_key, limit=10),
            "policy_effects": effects,
            "effective_local_observations": effective_local_observations,
            "inherited_observations": effective_inherited_observations,
            "effective_observations": effective_local_observations + effective_inherited_observations,
            "effective_decisions": effective_decisions,
            "pack_excluded_keys": pack_excluded,
            "retrieval_excluded_keys": retrieval_excluded,
            "keep_priority_keys": keep_priority,
            "repair_proposals": [],
        }

    def project_brief(self, project_key: str, *, session_id: int | None = None) -> dict[str, Any] | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        if session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        project_id = int(project["id"])
        governance = self._effective_governance(project_key, session_id=session_id)
        counts = self.conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM sessions WHERE project_id = ?) AS sessions,
              (SELECT COUNT(*) FROM turns t JOIN sessions s ON s.id = t.session_id WHERE s.project_id = ?) AS turns,
              (SELECT COUNT(*) FROM observations WHERE project_id = ?) AS observations,
              (SELECT COUNT(*) FROM decisions WHERE project_id = ? AND status = 'active') AS active_decisions
            """,
            (project_id, project_id, project_id, project_id),
        ).fetchone()
        recent = self.recent_observations(project_key=project_key, limit=5, session_id=session_id)
        decisions = governance["effective_decisions"][:5]
        return {
            "project": dict(project),
            "counts": dict(counts),
            "session_filter": self.get_session(session_id) if session_id is not None else None,
            "recent_observations": recent,
            "recent_decisions": [dict(row) for row in decisions],
            "operational_state": self.operational_state(project_key, session_id=session_id),
            "open_work": self.open_work_report(project_key, session_id=session_id),
            "completion_check": self.completion_check(project_key, session_id=session_id),
            "recent_changes": self.recent_changes(project_key, session_id=session_id),
            "scope_guard": self.scope_guard(project_key, session_id=session_id),
            "context_metrics": self.context_metrics_summary(project_key),
            "closure_metrics": self.closure_metrics_summary(project_key),
            "health_preview": self.health_report(project_key, record=False),
            "latest_health": self.latest_health_report(project_key),
            "snapshots": self.list_snapshots(project_key, limit=5),
            "policies": governance["local_policies"],
            "effective_policies": governance["effective_policies"],
            "inheritances": governance["inheritances"],
            "repairs": governance["repairs"],
            "policy_effects": governance["policy_effects"],
            "repair_proposals": self._repair_proposals_from_health(project_key, record_if_missing=False),
        }

    def recent_decisions(
        self,
        project_key: str,
        limit: int = 10,
        *,
        session_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        session_filter = ""
        params: list[Any] = [project_key]
        if session_id is not None:
            session_filter = "AND o.session_id = ?"
            params.append(int(session_id))
        params.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT d.id, d.title, d.decision_text, d.status, d.updated_at
            FROM decisions d
            JOIN projects p ON p.id = d.project_id
            JOIN observations o ON o.id = d.source_observation_id
            WHERE p.project_key = ? {session_filter}
            ORDER BY d.updated_at DESC, d.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def project_revision(self, project_key: str) -> dict[str, Any] | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        project_id = int(project["id"])
        row = self.conn.execute(
            """
            SELECT
              p.updated_at AS project_updated_at,
              (SELECT MAX(o.updated_at) FROM observations o WHERE o.project_id = p.id) AS latest_observation_at,
              (SELECT MAX(d.updated_at) FROM decisions d WHERE d.project_id = p.id) AS latest_decision_at,
              (SELECT MAX(c.generated_at) FROM context_sync_events c WHERE c.project_id = p.id) AS latest_sync_at,
              (SELECT MAX(h.generated_at) FROM health_reports h WHERE h.project_id = p.id) AS latest_health_at,
              (SELECT COUNT(*) FROM memory_policies mp WHERE mp.project_id = p.id) AS policies_count,
              (SELECT COUNT(*) FROM project_inheritances pi WHERE pi.target_project_id = p.id) AS inheritances_count,
              (SELECT COUNT(*) FROM repair_events re WHERE re.project_id = p.id) AS repairs_count
            FROM projects p
            WHERE p.id = ?
            """,
            (project_id,),
        ).fetchone()
        data = dict(row)
        data["project_key"] = project_key
        return data

    def operational_observations(self, project_key: str, limit: int = 80) -> list[dict[str, Any]]:
        return self._operational_observations(project_key, limit=limit)

    def _operational_observations(
        self,
        project_key: str,
        *,
        limit: int = 80,
        before: str | None = None,
        after: str | None = None,
        session_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        placeholders = ",".join("?" for _ in STATEFUL_OBSERVATION_TYPES)
        filters = ["p.project_key = ?", f"o.type IN ({placeholders})"]
        params: list[Any] = [project_key, *sorted(STATEFUL_OBSERVATION_TYPES)]
        if session_id is not None:
            filters.append("o.session_id = ?")
            params.append(int(session_id))
        if before is not None:
            filters.append("o.updated_at < ?")
            params.append(before)
        if after is not None:
            filters.append("o.updated_at > ?")
            params.append(after)
        fetch_limit = limit if session_id is not None else min(max(limit * 5, limit + 40), 1000)
        params.append(fetch_limit)
        rows = self.conn.execute(
            f"""
            SELECT
              o.id,
              p.id AS project_id,
              p.project_key,
              p.root_path AS project_root_path,
              o.session_id,
              s.external_session_id,
              s.cwd,
              s.runtime,
              s.metadata_json,
              o.turn_id,
              o.type,
              o.title,
              o.summary,
              o.detail,
              o.status,
              o.updated_at,
              COALESCE(t.captured_at, o.updated_at) AS last_captured_turn_at
            FROM observations o
            JOIN projects p ON p.id = o.project_id
            LEFT JOIN sessions s ON s.id = o.session_id
            LEFT JOIN turns t ON t.id = o.turn_id
            WHERE {' AND '.join(filters)}
            ORDER BY o.updated_at DESC, o.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        items = self._enrich_observation_items(
            [dict(row) for row in rows],
            session_filter_applied=session_id is not None,
            retrieval_scope="session" if session_id is not None else "project",
        )
        return self._filter_cross_project_capture_items(
            items,
            session_filter_applied=session_id is not None,
        )[:limit]

    def operational_state(self, project_key: str, *, session_id: int | None = None) -> dict[str, Any] | None:
        if self._project_row(project_key) is None:
            return None
        governance = self._effective_governance(project_key, session_id=session_id)
        return derive_operational_state(governance["effective_observations"][:160])

    def open_work_report(self, project_key: str, *, session_id: int | None = None) -> dict[str, Any] | None:
        state = self.operational_state(project_key, session_id=session_id)
        if state is None:
            return None
        report = build_open_work_report(state)
        if session_id is not None:
            report["session_filter"] = self.get_session(session_id)
        return report

    def completion_check(
        self,
        project_key: str,
        *,
        session_id: int | None = None,
        record: bool = False,
        event_kind: str = "check",
        turn_id: int | None = None,
    ) -> dict[str, Any] | None:
        state = self.operational_state(project_key, session_id=session_id)
        if state is None:
            return None
        result = build_completion_check(state)
        if session_id is not None:
            result["session_filter"] = self.get_session(session_id)
        if record:
            self.record_closure_event(
                project_key=project_key,
                turn_id=turn_id,
                event_kind=event_kind,
                completion_check=result,
            )
        return result

    def _last_successful_context_sync(self, project_key: str) -> dict[str, Any] | None:
        rows = self._successful_context_syncs(project_key, limit=1)
        return rows[0] if rows else None

    def _successful_context_syncs(self, project_key: str, limit: int = 2) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT c.id, c.generated_at, c.budget, c.target_path
            FROM context_sync_events c
            JOIN projects p ON p.id = c.project_id
            WHERE p.project_key = ? AND c.skipped = 0
            ORDER BY c.generated_at DESC, c.id DESC
            LIMIT ?
            """,
            (project_key, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def _recent_changes_baseline_sync(self, project_key: str) -> tuple[dict[str, Any] | None, str]:
        latest_change_at = self._latest_meaningful_change_at(project_key)
        if latest_change_at is not None:
            row = self.conn.execute(
                """
                SELECT c.id, c.generated_at, c.budget, c.target_path
                FROM context_sync_events c
                JOIN projects p ON p.id = c.project_id
                WHERE p.project_key = ? AND c.skipped = 0 AND c.generated_at < ?
                ORDER BY c.generated_at DESC, c.id DESC
                LIMIT 1
                """,
                (project_key, latest_change_at),
            ).fetchone()
            if row is not None:
                return dict(row), "sync_before_latest_meaningful_change"
        syncs = self._successful_context_syncs(project_key, limit=2)
        if len(syncs) >= 2:
            return syncs[1], "previous_successful_context_sync"
        if len(syncs) == 1:
            return syncs[0], "last_successful_context_sync"
        return None, "project_start"

    def _latest_meaningful_change_at(self, project_key: str) -> str | None:
        placeholders = ",".join("?" for _ in MEANINGFUL_CHANGE_TYPES)
        row = self.conn.execute(
            f"""
            SELECT MAX(o.updated_at) AS latest_change_at
            FROM observations o
            JOIN projects p ON p.id = o.project_id
            WHERE p.project_key = ? AND o.type IN ({placeholders})
            """,
            [project_key, *MEANINGFUL_CHANGE_TYPES],
        ).fetchone()
        if row is None:
            return None
        return row["latest_change_at"]

    def record_context_sync(
        self,
        *,
        project_key: str,
        target_path: str | None,
        skipped: bool,
        reason: str | None,
        stats: dict[str, Any],
    ) -> int | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        inserted_id: int | None = None
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO context_sync_events(
                  project_id, target_path, skipped, reason, source_char_count, pack_char_count,
                  approx_source_tokens, approx_pack_tokens, compression_ratio, budget, budget_reason, build_ms, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(project["id"]),
                    target_path,
                    1 if skipped else 0,
                    reason,
                    int(stats.get("source_char_count") or 0),
                    int(stats.get("pack_char_count") or 0),
                    int(stats.get("approx_source_tokens") or 0),
                    int(stats.get("approx_pack_tokens") or 0),
                    float(stats.get("compression_ratio") or 0.0),
                    str(stats.get("budget") or "normal"),
                    stats.get("budget_reason"),
                    float(stats.get("build_ms") or 0.0),
                    self._now(),
                ),
            )
            inserted_id = int(cur.lastrowid)
        latest_turn = self._latest_turn_source(int(project["id"]))
        self.record_provenance(
            memory_kind="context_sync",
            memory_id=int(inserted_id),
            project_id=int(project["id"]),
            session_id=int(latest_turn["session_id"]) if latest_turn else None,
            turn_id=int(latest_turn["turn_id"]) if latest_turn else None,
            observation_id=None,
            turn_hash=str(latest_turn["content_hash"]) if latest_turn and latest_turn.get("content_hash") else None,
            model_name=str(latest_turn["model_name"]) if latest_turn and latest_turn.get("model_name") else None,
            cwd=str(latest_turn["cwd"]) if latest_turn and latest_turn.get("cwd") else None,
            source_span={
                "target_path": target_path,
                "skipped": skipped,
                "reason": reason,
                "stats": stats,
            },
        )
        return inserted_id

    def recent_context_sync_events(self, project_key: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT c.id, c.target_path, c.skipped, c.reason, c.source_char_count, c.pack_char_count,
                   c.approx_source_tokens, c.approx_pack_tokens, c.compression_ratio, c.budget, c.budget_reason, c.build_ms, c.generated_at
            FROM context_sync_events c
            JOIN projects p ON p.id = c.project_id
            WHERE p.project_key = ?
            ORDER BY c.generated_at DESC, c.id DESC
            LIMIT ?
            """,
            (project_key, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def context_metrics_summary(self, project_key: str) -> dict[str, Any] | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        project_id = int(project["id"])
        row = self.conn.execute(
            """
            SELECT
              COUNT(*) AS total_events,
              SUM(CASE WHEN skipped = 0 THEN 1 ELSE 0 END) AS synced_events,
              SUM(CASE WHEN skipped = 1 THEN 1 ELSE 0 END) AS skipped_events,
              ROUND(AVG(compression_ratio), 3) AS avg_compression_ratio,
              ROUND(AVG(build_ms), 2) AS avg_build_ms,
              MAX(build_ms) AS max_build_ms,
              MAX(generated_at) AS last_generated_at
            FROM context_sync_events
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
        result = dict(row)
        budget_rows = self.conn.execute(
            """
            SELECT budget, COUNT(*) AS event_count, ROUND(AVG(compression_ratio), 3) AS avg_ratio
            FROM context_sync_events
            WHERE project_id = ?
            GROUP BY budget
            ORDER BY budget
            """,
            (project_id,),
        ).fetchall()
        result["budget_counts"] = {row["budget"]: row["event_count"] for row in budget_rows}
        result["avg_compression_ratio_by_budget"] = {
            row["budget"]: row["avg_ratio"] for row in budget_rows if row["avg_ratio"] is not None
        }
        result["recent_events"] = self.recent_context_sync_events(project_key, limit=5)
        return result

    def record_closure_event(
        self,
        *,
        project_key: str,
        turn_id: int | None,
        event_kind: str,
        completion_check: dict[str, Any],
    ) -> None:
        project = self._project_row(project_key)
        if project is None:
            return
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO closure_check_events(
                  project_id, turn_id, event_kind, passed, reasons_json, pending_count, blocker_count,
                  dod_missing_count, evidence_count, completion_claim_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(project["id"]),
                    turn_id,
                    event_kind,
                    1 if completion_check.get("done") else 0,
                    self._json(completion_check.get("reasons") or []),
                    int(completion_check.get("pending_count") or 0),
                    int(completion_check.get("blocker_count") or 0),
                    int(completion_check.get("dod_missing_count") or 0),
                    int(completion_check.get("evidence_count") or 0),
                    int(completion_check.get("completion_claim_count") or 0),
                    self._now(),
                ),
            )

    def recent_closure_events(self, project_key: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT c.id, c.turn_id, c.event_kind, c.passed, c.reasons_json, c.pending_count, c.blocker_count,
                   c.dod_missing_count, c.evidence_count, c.completion_claim_count, c.created_at
            FROM closure_check_events c
            JOIN projects p ON p.id = c.project_id
            WHERE p.project_key = ?
            ORDER BY c.created_at DESC, c.id DESC
            LIMIT ?
            """,
            (project_key, limit),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
            items.append(item)
        return items

    def closure_metrics_summary(self, project_key: str) -> dict[str, Any] | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        rows = self.conn.execute(
            """
            SELECT event_kind, passed, reasons_json, pending_count, blocker_count,
                   dod_missing_count, evidence_count, completion_claim_count, created_at
            FROM closure_check_events
            WHERE project_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (int(project["id"]),),
        ).fetchall()
        items = []
        reason_counts: dict[str, int] = {}
        mismatch_events = 0
        passed_checks = 0
        failed_checks = 0
        for row in rows:
            item = dict(row)
            reasons = json.loads(item["reasons_json"] or "[]")
            item["reasons"] = reasons
            items.append(item)
            if item["event_kind"] == "mismatch":
                mismatch_events += 1
            if item["passed"]:
                passed_checks += 1
            else:
                failed_checks += 1
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        return {
            "total_events": len(items),
            "mismatch_events": mismatch_events,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "reason_counts": reason_counts,
            "recent_events": self.recent_closure_events(project_key, limit=5),
        }

    def health_report(self, project_key: str, *, record: bool = False) -> dict[str, Any] | None:
        governance = self._effective_governance(project_key)
        state = self.operational_state(project_key)
        if state is None:
            return None
        completion_check = self.completion_check(project_key, record=False)
        if completion_check is None:
            return None
        observations = governance["effective_observations"][:240]
        report = build_health_report(
            project_key=project_key,
            operational_state=state,
            operational_observations=observations,
            completion_check=completion_check,
        )
        if record:
            self.record_health_report(project_key=project_key, report=report)
        return report

    def record_health_report(self, *, project_key: str, report: dict[str, Any]) -> int | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        inserted_id: int | None = None
        details = {
            "duplicates": report.get("duplicates") or [],
            "contradictions": report.get("contradictions") or [],
            "stale_items": report.get("stale_items") or [],
            "suggestions": report.get("suggestions") or [],
        }
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO health_reports(
                  project_id, score, duplicate_count, contradiction_count, stale_item_count,
                  dod_total_count, dod_missing_count, dod_coverage_ratio, open_work_count,
                  closure_mismatch, details_json, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(project["id"]),
                    int(report.get("score") or 0),
                    int(report.get("duplicate_count") or 0),
                    int(report.get("contradiction_count") or 0),
                    int(report.get("stale_item_count") or 0),
                    int(report.get("dod_total_count") or 0),
                    int(report.get("dod_missing_count") or 0),
                    float(report.get("dod_coverage_ratio") or 0.0),
                    int(report.get("open_work_count") or 0),
                    1 if report.get("closure_mismatch") else 0,
                    self._json(details),
                    str(report.get("generated_at") or self._now()),
                ),
            )
            inserted_id = int(cur.lastrowid)
        latest_turn = self._latest_turn_source(int(project["id"]))
        self.record_provenance(
            memory_kind="health_report",
            memory_id=int(inserted_id),
            project_id=int(project["id"]),
            session_id=int(latest_turn["session_id"]) if latest_turn else None,
            turn_id=int(latest_turn["turn_id"]) if latest_turn else None,
            observation_id=None,
            turn_hash=str(latest_turn["content_hash"]) if latest_turn and latest_turn.get("content_hash") else None,
            model_name=str(latest_turn["model_name"]) if latest_turn and latest_turn.get("model_name") else None,
            cwd=str(latest_turn["cwd"]) if latest_turn and latest_turn.get("cwd") else None,
            source_span={
                "score": report.get("score"),
                "suggestions": report.get("suggestions") or [],
            },
        )
        return inserted_id

    def latest_health_report(self, project_key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT h.*
            FROM health_reports h
            JOIN projects p ON p.id = h.project_id
            WHERE p.project_key = ?
            ORDER BY h.generated_at DESC, h.id DESC
            LIMIT 1
            """,
            (project_key,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        details = self._load_json(result.pop("details_json", None), {})
        result.update(details)
        result["closure_mismatch"] = bool(result.get("closure_mismatch"))
        return result

    def _last_context_sync_event_id(self, project_key: str) -> int | None:
        row = self.conn.execute(
            """
            SELECT c.id
            FROM context_sync_events c
            JOIN projects p ON p.id = c.project_id
            WHERE p.project_key = ?
            ORDER BY c.generated_at DESC, c.id DESC
            LIMIT 1
            """,
            (project_key,),
        ).fetchone()
        return int(row["id"]) if row is not None else None

    def snapshot_create(self, project_key: str, label: str, *, session_id: int | None = None) -> dict[str, Any] | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        resolved_session_id = (
            self._resolve_session_id(project_key, session_id=session_id)
            if session_id is not None
            else None
        )
        session = self.get_session(resolved_session_id) if resolved_session_id is not None else None
        state = self.operational_state(project_key, session_id=resolved_session_id)
        open_work = self.open_work_report(project_key, session_id=resolved_session_id)
        completion_check = self.completion_check(project_key, session_id=resolved_session_id, record=False)
        recent_changes = self.recent_changes(project_key, session_id=resolved_session_id)
        scope_guard = self.scope_guard(project_key, session_id=resolved_session_id)
        context_pack = self.context_pack(project_key, budget="auto", session_id=resolved_session_id)
        health = self.health_report(project_key, record=False)
        if state is None or open_work is None or completion_check is None or recent_changes is None or scope_guard is None or context_pack is None or health is None:
            return None
        created_at = self._now()
        payload = {
            "snapshot_version": 1,
            "project": dict(project),
            "label": label,
            "created_at": created_at,
            "operational_state": state,
            "open_work": open_work,
            "completion_check": completion_check,
            "recent_changes": recent_changes,
            "scope_guard": scope_guard,
            "context_pack": context_pack,
            "context_metrics": self.context_metrics_summary(project_key),
            "closure_metrics": self.closure_metrics_summary(project_key),
            "health": health,
            "recent_decisions": self.recent_decisions(project_key, limit=8, session_id=resolved_session_id),
        }
        raw = self._json(payload)
        snapshot_hash = sha256(raw.encode("utf-8")).hexdigest()
        file_name = f"{created_at[:19].replace(':', '').replace('-', '')}__{self._snapshot_slug(label)}__{snapshot_hash[:12]}.json"
        snapshot_path = self._snapshot_dir() / file_name
        snapshot_path.write_text(raw, encoding="utf-8")
        inserted_id: int | None = None
        sync_event_id = self._last_context_sync_event_id(project_key)
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO memory_snapshots(
                  project_id, label, snapshot_hash, snapshot_path, created_from_sync_event_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(project["id"]),
                    label,
                    snapshot_hash,
                    str(snapshot_path),
                    sync_event_id,
                    created_at,
                ),
            )
            inserted_id = int(cur.lastrowid)
        latest_turn = (
            self._session_latest_turn_source(resolved_session_id)
            if resolved_session_id is not None
            else None
        )
        provenance_confidence = "high" if resolved_session_id is not None else "low"
        provenance_warning = (
            None
            if resolved_session_id is not None
            else "No session_id was provided; snapshot was not associated with the latest project turn."
        )
        self.record_provenance(
            memory_kind="snapshot",
            memory_id=int(inserted_id),
            project_id=int(project["id"]),
            session_id=resolved_session_id,
            turn_id=int(latest_turn["turn_id"]) if latest_turn else None,
            observation_id=None,
            turn_hash=str(latest_turn["content_hash"]) if latest_turn and latest_turn.get("content_hash") else None,
            model_name=str(latest_turn["model_name"]) if latest_turn and latest_turn.get("model_name") else None,
            cwd=str(latest_turn["cwd"]) if latest_turn and latest_turn.get("cwd") else None,
            source_span={
                "label": label,
                "snapshot_hash": snapshot_hash,
                "created_from_sync_event_id": sync_event_id,
                "provenance_confidence": provenance_confidence,
                "provenance_warning": provenance_warning,
                "session_id": resolved_session_id,
                "external_session_id": session.get("external_session_id") if session else None,
                "display_label": session.get("display_label") if session else None,
            },
        )
        return {
            "id": inserted_id,
            "snapshot_id": inserted_id,
            "project_key": project_key,
            "label": label,
            "snapshot_hash": snapshot_hash,
            "snapshot_path": str(snapshot_path),
            "created_from_sync_event_id": sync_event_id,
            "session_id": resolved_session_id,
            "external_session_id": session.get("external_session_id") if session else None,
            "cwd": session.get("cwd") if session else None,
            "project_root_path": project["root_path"],
            "display_label": session.get("display_label") if session else None,
            "provenance_confidence": provenance_confidence,
            "provenance_warning": provenance_warning,
            "created_at": created_at,
        }

    def list_snapshots(self, project_key: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
              s.*,
              p.project_key,
              p.root_path AS project_root_path,
              mp.session_id,
              mp.turn_id,
              mp.cwd AS provenance_cwd,
              mp.source_span_json,
              sess.runtime,
              sess.external_session_id,
              sess.cwd AS session_cwd,
              sess.metadata_json,
              (
                SELECT t_first.input_messages_json
                FROM turns t_first
                WHERE t_first.session_id = sess.id
                ORDER BY t_first.captured_at ASC, t_first.id ASC
                LIMIT 1
              ) AS first_input_messages_json,
              (SELECT COUNT(*) FROM turns t WHERE t.session_id = sess.id) AS turn_count,
              (SELECT COUNT(*) FROM observations o WHERE o.session_id = sess.id) AS observation_count,
              COALESCE((SELECT MAX(t.captured_at) FROM turns t WHERE t.session_id = sess.id), sess.started_at) AS last_turn_at
            FROM memory_snapshots s
            JOIN projects p ON p.id = s.project_id
            LEFT JOIN memory_provenance mp ON mp.memory_kind = 'snapshot' AND mp.memory_id = s.id
            LEFT JOIN sessions sess ON sess.id = mp.session_id
            WHERE p.project_key = ?
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT ?
            """,
            (project_key, limit),
        ).fetchall()
        snapshots: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            source_span = self._load_json(item.pop("source_span_json", None), {})
            if not isinstance(source_span, dict):
                source_span = {}
            item["snapshot_id"] = item["id"]
            item["cwd"] = item.pop("session_cwd", None) or item.pop("provenance_cwd", None)
            item["provenance_confidence"] = source_span.get("provenance_confidence", "unknown")
            item["provenance_warning"] = source_span.get("provenance_warning")
            metadata_json = item.get("metadata_json")
            if item.get("session_id") is not None:
                session_preview = self._session_preview({
                    "id": item["session_id"],
                    "project_id": item["project_id"],
                    "runtime": item.get("runtime"),
                    "external_session_id": item.get("external_session_id"),
                    "started_at": item.get("created_at"),
                    "ended_at": None,
                    "cwd": item.get("cwd"),
                    "metadata_json": metadata_json,
                    "first_input_messages_json": item.get("first_input_messages_json"),
                    "turn_count": item.get("turn_count") or 0,
                    "observation_count": item.get("observation_count") or 0,
                    "last_turn_at": item.get("last_turn_at"),
                })
                item["display_label"] = session_preview.get("display_label")
            else:
                item["display_label"] = None
            item.pop("metadata_json", None)
            item.pop("first_input_messages_json", None)
            snapshots.append(item)
        return snapshots

    def snapshot_restore(self, project_key: str, snapshot_id: int) -> dict[str, Any] | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        row = self.conn.execute(
            """
            SELECT s.*
            FROM memory_snapshots s
            JOIN projects p ON p.id = s.project_id
            WHERE p.project_key = ? AND s.id = ?
            """,
            (project_key, snapshot_id),
        ).fetchone()
        if row is None:
            return None
        snapshot = dict(row)
        snapshot_path = Path(snapshot["snapshot_path"])
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")
        payload = self._load_json(snapshot_path.read_text(encoding="utf-8"), {})
        context_pack = payload.get("context_pack") or {}
        text = str(context_pack.get("text") or "").strip()
        if not text:
            raise ValueError("Snapshot does not contain a reusable context pack")
        root_path_value = project["root_path"]
        root_path = Path(str(root_path_value)) if root_path_value else None
        target_path = None
        if root_path and root_path.exists() and root_path.is_dir():
            from codex_agent_mem.project_doc import choose_project_doc_path, render_managed_block, upsert_managed_block

            target_path = choose_project_doc_path(root_path)
            upsert_managed_block(target_path, render_managed_block(context_pack))
            self.record_context_sync(
                project_key=project_key,
                target_path=str(target_path),
                skipped=False,
                reason="snapshot_restore",
                stats=context_pack.get("stats") or {},
            )
        with self.conn:
            self.conn.execute(
                "UPDATE memory_snapshots SET restored_at = ? WHERE id = ?",
                (self._now(), snapshot_id),
            )
        return {
            "project_key": project_key,
            "snapshot_id": snapshot_id,
            "label": snapshot["label"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "restored": target_path is not None,
            "path": str(target_path) if target_path else None,
            "context_pack": context_pack,
        }

    def recent_changes(
        self,
        project_key: str,
        since: str | None = None,
        *,
        session_id: int | None = None,
    ) -> dict[str, Any] | None:
        if session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        current_state = self.operational_state(project_key, session_id=session_id)
        if current_state is None:
            return None
        baseline_source = "explicit_since" if since else "project_start"
        baseline_timestamp = since
        if baseline_timestamp is None:
            baseline_sync, baseline_source = self._recent_changes_baseline_sync(project_key)
            if baseline_sync is not None:
                baseline_timestamp = str(baseline_sync["generated_at"])

        previous_state = None
        if baseline_timestamp is not None:
            previous_state = derive_operational_state(
                self._operational_observations(
                    project_key,
                    before=baseline_timestamp,
                    limit=240,
                    session_id=session_id,
                )
            )

        decisions = self.recent_decisions(project_key, limit=10, session_id=session_id)
        if baseline_timestamp is not None:
            decisions = [item for item in decisions if (item.get("updated_at") or "") > baseline_timestamp]
        result = build_recent_changes(
            current_state=current_state,
            previous_state=previous_state,
            recent_decisions=decisions,
            since=baseline_timestamp,
            baseline_source=baseline_source,
        )
        if session_id is not None:
            result["session_filter"] = self.get_session(session_id)
        return result

    def scope_resolve(
        self,
        project_key: str,
        hint: str | None = None,
        *,
        current_cwd: str | None = None,
        repo_path: str | None = None,
        mentioned_files: list[str] | None = None,
        limit: int = 8,
    ) -> dict[str, Any] | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        limit = max(1, min(int(limit), 20))
        hint_text = _scope_hint_text(
            hint,
            current_cwd=current_cwd,
            repo_path=repo_path,
            mentioned_files=mentioned_files,
        )
        hint_folded = _fold_search_text(hint_text)
        hint_tokens = _meaningful_query_tokens(_search_tokens(hint_text))
        sessions = self._scope_sessions_for_project(project_key, limit=100)
        session_count = len(sessions)
        multiple_sessions_detected = session_count > 1

        candidates: list[dict[str, Any]] = []
        for index, session in enumerate(sessions):
            session_id = int(session["session_id"])
            raw_sub_scope = session.get("inferred_sub_scope")
            candidate_sub_scope = _recommended_narrowing_candidate(raw_sub_scope) or _recommended_narrowing_candidate(
                session.get("cwd")
            )
            score = 0
            signals: list[str] = []
            matched_tokens: set[str] = set()
            if hint_text:
                exact_fields = {
                    "inferred_sub_scope": candidate_sub_scope,
                    "cwd_leaf": _scope_path_leaf(session.get("cwd")),
                    "external_session_id": session.get("external_session_id"),
                }
                for signal_name, value in exact_fields.items():
                    folded_value = _fold_search_text(value)
                    if signal_name == "external_session_id":
                        if folded_value and folded_value == hint_folded:
                            score += 220
                            signals.append("external_session_id_literal_match")
                        continue
                    if folded_value and folded_value in hint_folded:
                        score += 60 if signal_name == "cwd_leaf" else 80
                        signals.append(f"{signal_name}_literal_match")

                for path_hint in (_scope_path_leaf(current_cwd), _scope_path_leaf(repo_path)):
                    if not path_hint:
                        continue
                    folded_path_hint = _fold_search_text(path_hint)
                    if folded_path_hint and folded_path_hint in {
                        _fold_search_text(candidate_sub_scope),
                        _fold_search_text(_scope_path_leaf(session.get("cwd"))),
                    }:
                        score += 100
                        signals.append("path_hint_exact_match")

                sub_scope_overlap = hint_tokens & _tag_components(candidate_sub_scope or "")
                if sub_scope_overlap:
                    score += min(len(sub_scope_overlap) * 30, 90)
                    signals.append("sub_scope_token_match")
                    matched_tokens.update(sub_scope_overlap)

                label_text = " ".join(
                    str(value or "")
                    for value in (
                        session.get("display_label"),
                        session.get("first_input_preview"),
                        session.get("first_operational_input_preview"),
                        session.get("external_session_id"),
                    )
                )
                label_overlap = hint_tokens & _meaningful_query_tokens(_search_tokens(label_text))
                if label_overlap:
                    score += min(len(label_overlap) * 8, 40)
                    signals.append("session_label_token_match")
                    matched_tokens.update(label_overlap)

            if hint_text and score <= 0:
                continue
            if not hint_text and candidate_sub_scope is None:
                continue
            candidate_query = _recommended_narrowing_candidate(candidate_sub_scope or raw_sub_scope)
            recommended_call = (
                f'mem_session_list(project_key, query="{candidate_query}")'
                if candidate_query
                else 'mem_session_list(project_key, query="<target sub-scope>")'
            )
            candidates.append(
                {
                    "session_id": session_id,
                    "external_session_id": session.get("external_session_id"),
                    "inferred_sub_scope": candidate_sub_scope or raw_sub_scope,
                    "display_label": session.get("display_label"),
                    "cwd": session.get("cwd"),
                    "last_turn_at": session.get("last_turn_at"),
                    "turn_count": session.get("turn_count"),
                    "observation_count": session.get("observation_count"),
                    "score": score,
                    "confidence": "low",
                    "signals_used": sorted(set(signals)),
                    "matched_tokens": sorted(matched_tokens),
                    "recommended_call": recommended_call,
                    "_recency_rank": index,
                }
            )

        candidates.sort(
            key=lambda item: (
                int(item["score"]),
                str(item.get("last_turn_at") or ""),
                -int(item.get("_recency_rank") or 0),
                int(item["session_id"]),
            ),
            reverse=True,
        )
        candidates = candidates[:limit]
        top_score = int(candidates[0]["score"]) if candidates else 0
        second_score = int(candidates[1]["score"]) if len(candidates) > 1 else 0
        top_confidence = _scope_confidence(top_score, second_score) if hint_text and candidates else "low"
        for candidate in candidates:
            candidate["confidence"] = _scope_confidence(int(candidate["score"]), second_score)
            candidate.pop("_recency_rank", None)

        lane_source = candidates if candidates else sessions
        candidate_lanes = _scope_lane_inventory(lane_source, second_score=second_score, limit=limit)
        candidate_sub_scopes = [str(item["inferred_sub_scope"]) for item in candidate_lanes]
        multiple_lanes_detected = len(candidate_lanes) > 1
        broad_scope_detected = multiple_sessions_detected or multiple_lanes_detected

        recommended_scope = None
        recommended_call = 'mem_session_list(project_key, query="<target sub-scope>")'
        routing_decision = "needs_hint"
        fallback_reason = (
            "Multiple persisted sessions exist; choose a target session/sub-scope before "
            "loading active context."
            if multiple_sessions_detected
            else "No hint was provided; choose a target sub-scope before loading active context."
        )
        do_not_fetch_project_wide_pack = broad_scope_detected
        next_action = (
            "Choose a target session/sub-scope before loading active context."
            if broad_scope_detected
            else "Project has one persisted session; project-wide startup is not broad."
        )
        if hint_text and not candidates:
            routing_decision = "no_match"
            fallback_reason = "No persisted session/sub-scope had enough explicit evidence for the hint."
            do_not_fetch_project_wide_pack = True
            next_action = "Inspect candidate_lanes or call mem_session_list with a clearer query; do not load a broad pack."
        elif hint_text and top_confidence == "high":
            best = candidates[0]
            recommended_scope = {
                "inferred_sub_scope": best.get("inferred_sub_scope"),
                "confidence": "high",
                "score": best["score"],
            }
            routing_decision = "lane_resolved"
            fallback_reason = (
                "Hint resolved to a high-confidence lane/sub-scope; choose a session_id from that lane."
            )
            recommended_call = best["recommended_call"]
            do_not_fetch_project_wide_pack = True
            next_action = "Call mem_session_list for the resolved lane, then mem_context_pack with session_id."
        elif hint_text and candidates:
            if len(candidate_lanes) == 1:
                routing_decision = "lane_resolved"
                lane = candidate_lanes[0]
                recommended_call = str(lane["recommended_call"])
                fallback_reason = (
                    "Hint resolved to one lane/sub-scope but not one session; choose a session_id from that lane."
                )
                next_action = "Call mem_session_list for the resolved lane, then mem_context_pack with session_id."
            else:
                routing_decision = "ambiguous"
                fallback_reason = (
                    "Hint produced candidates but not enough confidence to auto-select; choose one session_id explicitly."
                )
                next_action = "Choose one candidate lane/session before loading active context."
            do_not_fetch_project_wide_pack = True

        return {
            "project_key": project_key,
            "hint": str(hint or ""),
            "routing_decision": routing_decision,
            "recommended_scope": recommended_scope,
            "candidates": candidates,
            "candidate_lanes": candidate_lanes,
            "candidate_sub_scopes": candidate_sub_scopes,
            "session_count": session_count,
            "multiple_sessions_detected": multiple_sessions_detected,
            "multiple_lanes_detected": multiple_lanes_detected,
            "broad_scope_detected": broad_scope_detected,
            "confidence": top_confidence,
            "signals_used": sorted({signal for candidate in candidates for signal in candidate["signals_used"]}),
            "fallback_reason": fallback_reason,
            "recommended_call": recommended_call,
            "do_not_fetch_project_wide_pack": do_not_fetch_project_wide_pack,
            "next_action": next_action,
            "writes_performed": False,
        }

    def bootstrap_context(
        self,
        project_key: str,
        *,
        hint: str | None = None,
        thread_hint: str | None = None,
        chat_title: str | None = None,
        active_chat_label: str | None = None,
        current_cwd: str | None = None,
        repo_path: str | None = None,
        mentioned_files: list[str] | None = None,
        session_id: int | None = None,
        budget: str = "micro",
    ) -> dict[str, Any] | None:
        if session_id is not None:
            resolved_session_id = self._resolve_session_id(project_key, session_id=session_id)
            pack = self.context_pack(project_key, budget=budget, session_id=resolved_session_id)
            if pack is None:
                return None
            return {
                "project_key": project_key,
                "selection_mode": "explicit_session_id",
                "session_id": resolved_session_id,
                "scope_resolution": None,
                "context_pack": pack,
                "recommended_call": f"mem_context_pack(project_key, session_id={resolved_session_id})",
                "next_action": "Use the explicit session-scoped context pack.",
                "writes_performed": False,
            }
        effective_hint = _combine_scope_hints(hint, thread_hint, chat_title, active_chat_label)
        resolution = self.scope_resolve(
            project_key,
            hint=effective_hint,
            current_cwd=current_cwd,
            repo_path=repo_path,
            mentioned_files=mentioned_files,
            limit=8,
        )
        if resolution is None:
            return None
        if resolution.get("do_not_fetch_project_wide_pack"):
            routing_decision = str(resolution.get("routing_decision") or "needs_hint")
            selection_mode = "lane_needs_session_selection" if routing_decision == "lane_resolved" else "needs_narrowing"
            next_action = (
                "Choose a session from candidate_lanes, then call mem_context_pack with session_id."
                if routing_decision == "lane_resolved"
                else "Choose a target from candidate_lanes/candidate_sub_scopes before loading active context."
            )
            return {
                "project_key": project_key,
                "selection_mode": selection_mode,
                "session_id": None,
                "scope_resolution": resolution,
                "context_pack": None,
                "recommended_call": resolution.get(
                    "recommended_call",
                    'mem_session_list(project_key, query="<target sub-scope>")',
                ),
                "next_action": next_action,
                "writes_performed": False,
            }

        pack = self.context_pack(project_key, budget=budget)
        if pack is None:
            return None
        return {
            "project_key": project_key,
            "selection_mode": "project_wide",
            "session_id": None,
            "scope_resolution": resolution,
            "context_pack": pack,
            "recommended_call": "mem_context_pack(project_key)",
            "next_action": "Use the project-wide pack only if the project is not a multi-lane container.",
            "writes_performed": False,
        }

    def scope_guard(self, project_key: str, *, session_id: int | None = None) -> dict[str, Any] | None:
        state = self.operational_state(project_key, session_id=session_id)
        if state is None:
            return None
        check = self.completion_check(project_key, session_id=session_id, record=False)
        guard = build_scope_guard(state, check)
        if session_id is not None:
            guard["session_filter"] = self.get_session(session_id)
            guard["scope_mode"] = "session"
            guard["session_filter_applied"] = True
            guard["source_session_count"] = 1
            guard["multiple_sessions_detected"] = False
            guard["multiple_lanes_detected"] = False
            guard["broad_scope_detected"] = False
            guard["do_not_fetch_project_wide_pack"] = False
            guard["live_turn_awareness"] = False
            guard["memory_freshness"] = "persisted"
            return guard

        sessions = self._scope_sessions_for_project(project_key, limit=100)
        candidate_lanes = _scope_lane_inventory(sessions, limit=8)
        multiple_sessions_detected = len(sessions) > 1
        multiple_lanes_detected = len(candidate_lanes) > 1
        broad_scope_detected = multiple_sessions_detected or multiple_lanes_detected
        guard["scope_mode"] = "project"
        guard["session_filter_applied"] = False
        guard["source_session_count"] = len(sessions)
        guard["source_sessions"] = sessions[:6]
        guard["source_sessions_truncated"] = len(sessions) > 6
        guard["candidate_lanes"] = candidate_lanes
        guard["candidate_sub_scopes"] = [str(item["inferred_sub_scope"]) for item in candidate_lanes]
        guard["multiple_sessions_detected"] = multiple_sessions_detected
        guard["multiple_lanes_detected"] = multiple_lanes_detected
        guard["broad_scope_detected"] = broad_scope_detected
        guard["do_not_fetch_project_wide_pack"] = broad_scope_detected
        guard["active_objective_uncertain"] = broad_scope_detected
        guard["active_objective_suppressed"] = broad_scope_detected
        guard["active_objective_suppression_reason"] = (
            "project-wide scope has multiple persisted sessions or candidate lanes"
            if broad_scope_detected
            else None
        )
        guard["live_turn_awareness"] = False
        guard["memory_freshness"] = "persisted" if sessions else "unknown"
        if broad_scope_detected:
            guard["scope_warning"] = {
                "code": (
                    "multi_lane_project_scope"
                    if multiple_lanes_detected
                    else "multi_session_project_scope"
                ),
                "severity": "warn",
                "message": (
                    "Project-wide startup scope has multiple persisted sessions or "
                    "candidate lanes/sub-scopes."
                ),
                "recommendation": (
                    "Use mem_bootstrap_context or mem_session_list before loading "
                    "an active context pack."
                ),
            }
            guard["recommended_narrowing"] = {
                "reason": (
                    "project-wide startup scope spans multiple persisted sessions "
                    "or candidate lanes/sub-scopes"
                ),
                "candidate_sub_scopes": guard["candidate_sub_scopes"][:8],
                "next_steps": [
                    {
                        "tool": "mem_session_list",
                        "arguments": {
                            "project_key": project_key,
                            "query": "<target sub-scope>",
                        },
                        "then": "mem_context_pack(project_key, session_id=<chosen_session_id>)",
                    },
                    {
                        "tool": "mem_bootstrap_context",
                        "arguments": {
                            "project_key": project_key,
                            "hint": "<target sub-scope>",
                        },
                    },
                ],
                "confidence": "medium" if candidate_lanes else "low",
            }
        return guard

    def context_pack(
        self,
        project_key: str,
        max_chars: int | None = None,
        budget: str = "auto",
        session_id: int | None = None,
    ) -> dict[str, Any] | None:
        if session_id is not None:
            session_id = self._resolve_session_id(project_key, session_id=session_id)
        brief = self.project_brief(project_key, session_id=session_id)
        if brief is None:
            return None
        governance = self._effective_governance(project_key, session_id=session_id)
        summaries = [
            item
            for item in self.recent_observations(project_key=project_key, limit=12, session_id=session_id)
            if item.get("type") == "session_summary"
        ]
        summary_effects = evaluate_policy_effects(
            [self._policy_item_from_observation(item) for item in summaries],
            governance["effective_policies"],
            self._approved_repairs(project_key),
        )
        summaries = filter_items_by_policy(
            [dict(item, memory_kind="observation") for item in summaries],
            excluded_keys=set(summary_effects["pack_excluded_keys"]),
        )
        selected_budget = budget
        budget_reason = None
        if budget == "auto":
            selected_budget, budget_reason = choose_auto_budget(
                brief["operational_state"],
                max_chars=max_chars,
            )
        started = perf_counter()
        decisions = filter_items_by_policy(
            governance["effective_decisions"],
            excluded_keys=governance["pack_excluded_keys"],
        )[:8]
        candidate_pool_limit = 480 if session_id is None else 160
        observation_candidates = filter_items_by_policy(
            governance["effective_observations"],
            excluded_keys=governance["pack_excluded_keys"],
        )[:candidate_pool_limit]
        observation_candidates = [
            item
            for item in observation_candidates
            if not is_internal_prompt_noise(item_text(item))
        ]
        observation_candidates, dedupe_stats = dedupe_retrieval_items(observation_candidates)
        should_apply_dominance_guard = (
            session_id is None and len(self._source_session_ids(observation_candidates, [])) > 1
        )
        if should_apply_dominance_guard:
            observation_candidates, dominance_stats = cap_items_per_session(
                observation_candidates,
                max_items_per_session=8,
            )
        else:
            dominance_stats = {
                "dominance_guard_applied": False,
                "max_items_per_session": None,
                "protected_types": [],
                "protected_items_retained": 0,
                "sessions_capped": [],
            }
        pack_observations = observation_candidates[:160]
        source_turns = self.recent_turn_context(
            project_key=project_key,
            limit=max(len(summaries), 4),
            session_id=session_id,
        )
        scope_meta = self._context_scope_metadata(
            project_key,
            session_id=session_id,
            source_items=[*summaries, *pack_observations, *decisions],
            source_turns=source_turns,
        )
        scope_notice_lines = self._scope_notice_lines(scope_meta)
        if max_chars is not None and max_chars <= 600:
            scope_notice_lines = [
                line
                for line in scope_notice_lines
                if not line.startswith("Suggested narrowing:")
                and not line.startswith("No active objective selected:")
            ]
        operational_state = derive_operational_state(pack_observations)
        if scope_meta.get("active_objective_suppressed"):
            operational_state = dict(operational_state)
            operational_state["objective"] = None
            operational_state["user_requests"] = []
        result = build_context_pack(
            project=brief["project"],
            decisions=decisions,
            summaries=summaries,
            operational_state=operational_state,
            source_turns=source_turns,
            scope_notice_lines=scope_notice_lines,
            objective_title="Objective",
            budget=selected_budget,
            max_chars=max_chars,
            budget_reason=budget_reason,
        )
        source_sessions = scope_meta["source_sessions"]
        result["stats"]["scope_mode"] = scope_meta["scope_mode"]
        result["stats"]["session_filter_applied"] = scope_meta["session_filter_applied"]
        result["stats"]["source_session_count"] = scope_meta["source_session_count"]
        result["stats"]["source_sessions"] = [
            {
                "id": item.get("id"),
                "project_id": item.get("project_id"),
                "session_id": item.get("session_id") or item.get("id"),
                "runtime": item.get("runtime"),
                "external_session_id": item.get("external_session_id"),
                "cwd": item.get("cwd"),
                "turn_count": item.get("turn_count"),
                "observation_count": item.get("observation_count"),
                "last_turn_at": item.get("last_turn_at"),
                "first_input_preview": item.get("first_input_preview"),
                "display_label": item.get("display_label"),
                "label_quality": item.get("label_quality"),
                "inferred_sub_scope": item.get("inferred_sub_scope"),
                "producer_version": item.get("producer_version"),
                "capture_version_status": item.get("capture_version_status"),
                "capture_version_scope": item.get("capture_version_scope"),
            }
            for item in source_sessions
        ]
        result["stats"]["source_sessions_truncated"] = scope_meta["source_sessions_truncated"]
        result["stats"]["source_sub_scope_count"] = scope_meta["source_sub_scope_count"]
        result["stats"]["source_sub_scopes"] = scope_meta["source_sub_scopes"]
        result["stats"]["candidate_lanes"] = scope_meta["candidate_lanes"]
        result["stats"]["candidate_sub_scopes"] = scope_meta["candidate_sub_scopes"]
        result["stats"]["multiple_sessions_detected"] = scope_meta["multiple_sessions_detected"]
        result["stats"]["multiple_lanes_detected"] = scope_meta["multiple_lanes_detected"]
        result["stats"]["broad_scope_detected"] = scope_meta["broad_scope_detected"]
        result["stats"]["do_not_fetch_project_wide_pack"] = scope_meta["do_not_fetch_project_wide_pack"]
        result["stats"]["scope_warning"] = scope_meta["scope_warning"]
        if scope_meta.get("recommended_narrowing") is not None:
            result["stats"]["recommended_narrowing"] = scope_meta["recommended_narrowing"]
        result["stats"]["active_objective_uncertain"] = scope_meta["active_objective_uncertain"]
        result["stats"]["active_objective_suppressed"] = scope_meta["active_objective_suppressed"]
        result["stats"]["active_objective_suppression_reason"] = scope_meta["active_objective_suppression_reason"]
        result["stats"]["last_captured_turn_at"] = scope_meta["last_captured_turn_at"]
        result["stats"]["last_operational_capture_at"] = scope_meta["last_operational_capture_at"]
        result["stats"]["memory_age_seconds"] = scope_meta["memory_age_seconds"]
        result["stats"]["operational_memory_age_seconds"] = scope_meta["operational_memory_age_seconds"]
        result["stats"]["memory_freshness"] = scope_meta["memory_freshness"]
        result["stats"]["live_turn_awareness"] = scope_meta["live_turn_awareness"]
        result["stats"]["dedupe"] = dedupe_stats
        result["stats"]["dominance_guard"] = dominance_stats
        result["stats"]["selection_pool"] = {
            "candidate_pool_limit": candidate_pool_limit,
            "candidate_count_after_policy": len(observation_candidates),
            "final_observation_count": len(pack_observations),
        }
        excluded_count = len(governance["pack_excluded_keys"])
        inherited_count = len(governance["inheritances"])
        if excluded_count or inherited_count:
            notes: list[str] = []
            if excluded_count:
                notes.append(f"- Policy-governed selection excluded {excluded_count} item(s) from this pack.")
            if inherited_count:
                notes.append(f"- Active inheritance links contributing to continuity: {inherited_count}.")
            if notes:
                result["text"] = result["text"].rstrip() + "\n\n### Selection rules\n" + "\n".join(notes)
                result["stats"]["pack_char_count"] = len(result["text"])
                result["stats"]["approx_pack_tokens"] = max(1, (len(result["text"]) + 3) // 4)
                result["stats"]["compression_ratio"] = round(
                    len(result["text"]) / max(result["stats"]["source_char_count"], 1),
                    3,
                )
        result["stats"]["build_ms"] = round((perf_counter() - started) * 1000, 2)
        return result

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
