from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any

from codex_agent_mem.closure_control import build_completion_check, build_open_work_report
from codex_agent_mem.context_pack import build_context_pack, choose_auto_budget
from codex_agent_mem.ingest import classify_event, stable_hash
from codex_agent_mem.models import GenericEventEnvelope, Observation
from codex_agent_mem.operational_state import STATEFUL_OBSERVATION_TYPES, derive_operational_state
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


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
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


def _type_priority_case(column: str = "o.type") -> str:
    clauses = [f"WHEN '{name}' THEN {priority}" for name, priority in RETRIEVAL_TYPE_PRIORITY.items()]
    return f"CASE {column} {' '.join(clauses)} ELSE 50 END"


class CodexAgentMemStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = connect(db_path)
        schema_sql = files("codex_agent_mem").joinpath("schema.sql").read_text(encoding="utf-8")
        bootstrap(self.conn, schema_sql)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _project_name(project_key: str) -> str:
        return project_key.replace("-", " ").replace("_", " ").strip() or project_key

    def upsert_project(self, project_key: str, root_path: str | None) -> int:
        now = self._now()
        name = self._project_name(project_key)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO projects(project_key, name, root_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_key) DO UPDATE SET
                  name = excluded.name,
                  root_path = COALESCE(excluded.root_path, projects.root_path),
                  updated_at = excluded.updated_at
                """,
                (project_key, name, root_path, now, now),
            )
        row = self.conn.execute("SELECT id FROM projects WHERE project_key = ?", (project_key,)).fetchone()
        assert row is not None
        return int(row["id"])

    def upsert_session(self, project_id: int, event: GenericEventEnvelope) -> int:
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
                    self._json(event.metadata),
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
        return obs_id

    def ingest_event(self, raw_payload: dict[str, Any], event: GenericEventEnvelope) -> dict[str, Any]:
        project_id = self.upsert_project(event.project_key, event.cwd)
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

    def recent_observations(self, project_key: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        sql = """
        SELECT o.id, p.project_key, o.session_id, o.turn_id, o.type, o.title, o.summary, o.status, o.updated_at
        FROM observations o
        JOIN projects p ON p.id = o.project_id
        {where}
        ORDER BY o.updated_at DESC, o.id DESC
        LIMIT ?
        """
        params: list[Any] = []
        where = ""
        if project_key:
            where = "WHERE p.project_key = ?"
            params.append(project_key)
        params.append(limit)
        rows = self.conn.execute(sql.format(where=where), params).fetchall()
        return [dict(row) for row in rows]

    def search_observations(self, query: str, project_key: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if not query.strip():
            return self.recent_observations(project_key=project_key, limit=limit)
        params: list[Any] = [query]
        where = ""
        type_priority_sql = _type_priority_case("o.type")
        if project_key:
            where = "AND p.project_key = ?"
            params.append(project_key)
        params.append(limit)
        try:
            rows = self.conn.execute(
                f"""
                SELECT o.id, p.project_key, o.session_id, o.turn_id, o.type, o.title, o.summary, o.status, o.updated_at,
                       bm25(observations_fts) AS rank
                FROM observations_fts
                JOIN observations o ON o.id = observations_fts.rowid
                JOIN projects p ON p.id = o.project_id
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
            if project_key:
                where = "AND p.project_key = ?"
                params.append(project_key)
            params.append(limit)
            rows = self.conn.execute(
                f"""
                SELECT o.id, p.project_key, o.session_id, o.turn_id, o.type, o.title, o.summary, o.status, o.updated_at
                FROM observations o
                JOIN projects p ON p.id = o.project_id
                WHERE (o.title LIKE ? OR o.summary LIKE ? OR o.detail LIKE ?) {where}
                ORDER BY {type_priority_sql}, o.updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

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

    def list_sessions(self, project_key: str, limit: int = 50) -> list[dict[str, Any]]:
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
              (
                SELECT t_first.input_messages_json
                FROM turns t_first
                WHERE t_first.session_id = s.id
                ORDER BY t_first.captured_at ASC, t_first.id ASC
                LIMIT 1
              ) AS first_input_messages_json,
              COUNT(DISTINCT t.id) AS turn_count,
              COUNT(DISTINCT o.id) AS observation_count,
              MAX(t.captured_at) AS last_turn_at
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
            LEFT JOIN turns t ON t.session_id = s.id
            LEFT JOIN observations o ON o.session_id = s.id
            WHERE p.project_key = ?
            GROUP BY s.id
            ORDER BY COALESCE(MAX(t.captured_at), s.started_at) DESC, s.id DESC
            LIMIT ?
            """,
            (project_key, limit),
        ).fetchall()
        return [dict(row) for row in rows]

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
              MAX(t.captured_at) AS last_turn_at
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
              (
                SELECT t_first.input_messages_json
                FROM turns t_first
                WHERE t_first.session_id = s.id
                ORDER BY t_first.captured_at ASC, t_first.id ASC
                LIMIT 1
              ) AS first_input_messages_json,
              (SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id) AS turn_count,
              (SELECT COUNT(*) FROM observations o WHERE o.session_id = s.id) AS observation_count
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()
        return dict(row) if row is not None else None

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

    def recent_turn_context(self, project_key: str, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT t.id, t.input_messages_json, t.assistant_message, t.captured_at
            FROM turns t
            JOIN sessions s ON s.id = t.session_id
            JOIN projects p ON p.id = s.project_id
            WHERE p.project_key = ?
            ORDER BY t.captured_at DESC, t.id DESC
            LIMIT ?
            """,
            (project_key, limit),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            try:
                payload["input_messages"] = json.loads(payload.get("input_messages_json") or "[]")
            except json.JSONDecodeError:
                payload["input_messages"] = []
            items.append(payload)
        return items

    def _project_row(self, project_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT id, project_key, name, root_path, updated_at FROM projects WHERE project_key = ?",
            (project_key,),
        ).fetchone()

    def project_brief(self, project_key: str) -> dict[str, Any] | None:
        project = self._project_row(project_key)
        if project is None:
            return None
        project_id = int(project["id"])
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
        recent = self.recent_observations(project_key=project_key, limit=5)
        decisions = self.conn.execute(
            "SELECT id, title, decision_text, status, updated_at FROM decisions WHERE project_id = ? ORDER BY updated_at DESC LIMIT 5",
            (project_id,),
        ).fetchall()
        return {
            "project": dict(project),
            "counts": dict(counts),
            "recent_observations": recent,
            "recent_decisions": [dict(row) for row in decisions],
            "operational_state": self.operational_state(project_key),
            "open_work": self.open_work_report(project_key),
            "completion_check": self.completion_check(project_key),
            "recent_changes": self.recent_changes(project_key),
            "scope_guard": self.scope_guard(project_key),
            "context_metrics": self.context_metrics_summary(project_key),
            "closure_metrics": self.closure_metrics_summary(project_key),
        }

    def recent_decisions(self, project_key: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT d.id, d.title, d.decision_text, d.status, d.updated_at
            FROM decisions d
            JOIN projects p ON p.id = d.project_id
            WHERE p.project_key = ?
            ORDER BY d.updated_at DESC, d.id DESC
            LIMIT ?
            """,
            (project_key, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def operational_observations(self, project_key: str, limit: int = 80) -> list[dict[str, Any]]:
        return self._operational_observations(project_key, limit=limit)

    def _operational_observations(
        self,
        project_key: str,
        *,
        limit: int = 80,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in STATEFUL_OBSERVATION_TYPES)
        filters = ["p.project_key = ?", f"o.type IN ({placeholders})"]
        params: list[Any] = [project_key, *sorted(STATEFUL_OBSERVATION_TYPES)]
        if before is not None:
            filters.append("o.updated_at < ?")
            params.append(before)
        if after is not None:
            filters.append("o.updated_at > ?")
            params.append(after)
        params.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT o.id, o.type, o.title, o.summary, o.detail, o.status, o.updated_at
            FROM observations o
            JOIN projects p ON p.id = o.project_id
            WHERE {' AND '.join(filters)}
            ORDER BY o.updated_at DESC, o.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def operational_state(self, project_key: str) -> dict[str, Any] | None:
        if self._project_row(project_key) is None:
            return None
        return derive_operational_state(self._operational_observations(project_key, limit=120))

    def open_work_report(self, project_key: str) -> dict[str, Any] | None:
        state = self.operational_state(project_key)
        if state is None:
            return None
        return build_open_work_report(state)

    def completion_check(
        self,
        project_key: str,
        *,
        record: bool = False,
        event_kind: str = "check",
        turn_id: int | None = None,
    ) -> dict[str, Any] | None:
        state = self.operational_state(project_key)
        if state is None:
            return None
        result = build_completion_check(state)
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
    ) -> None:
        project = self._project_row(project_key)
        if project is None:
            return
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO context_sync_events(
                  project_id, target_path, skipped, reason, source_char_count, pack_char_count,
                  approx_source_tokens, approx_pack_tokens, compression_ratio, budget, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    self._now(),
                ),
            )

    def recent_context_sync_events(self, project_key: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT c.id, c.target_path, c.skipped, c.reason, c.source_char_count, c.pack_char_count,
                   c.approx_source_tokens, c.approx_pack_tokens, c.compression_ratio, c.budget, c.generated_at
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

    def recent_changes(self, project_key: str, since: str | None = None) -> dict[str, Any] | None:
        current_state = self.operational_state(project_key)
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
                self._operational_observations(project_key, before=baseline_timestamp, limit=240)
            )

        decisions = self.recent_decisions(project_key, limit=10)
        if baseline_timestamp is not None:
            decisions = [item for item in decisions if (item.get("updated_at") or "") > baseline_timestamp]
        return build_recent_changes(
            current_state=current_state,
            previous_state=previous_state,
            recent_decisions=decisions,
            since=baseline_timestamp,
            baseline_source=baseline_source,
        )

    def scope_guard(self, project_key: str) -> dict[str, Any] | None:
        state = self.operational_state(project_key)
        if state is None:
            return None
        check = self.completion_check(project_key, record=False)
        return build_scope_guard(state, check)

    def context_pack(
        self,
        project_key: str,
        max_chars: int | None = None,
        budget: str = "auto",
    ) -> dict[str, Any] | None:
        brief = self.project_brief(project_key)
        if brief is None:
            return None
        summaries = [
            item
            for item in self.recent_observations(project_key=project_key, limit=12)
            if item.get("type") == "session_summary"
        ]
        selected_budget = budget
        budget_reason = None
        if budget == "auto":
            selected_budget, budget_reason = choose_auto_budget(
                brief["operational_state"],
                max_chars=max_chars,
            )
        return build_context_pack(
            project=brief["project"],
            decisions=self.recent_decisions(project_key=project_key, limit=8),
            summaries=summaries,
            operational_state=brief["operational_state"],
            source_turns=self.recent_turn_context(project_key=project_key, limit=max(len(summaries), 4)),
            budget=selected_budget,
            max_chars=max_chars,
            budget_reason=budget_reason,
        )

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
