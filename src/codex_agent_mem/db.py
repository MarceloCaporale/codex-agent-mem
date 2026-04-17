from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Any

from codex_agent_mem.ingest import classify_event, stable_hash
from codex_agent_mem.models import GenericEventEnvelope, Observation


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def bootstrap(conn: sqlite3.Connection, schema_sql: str) -> None:
    conn.executescript(schema_sql)
    conn.commit()


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
            "SELECT id, project_key, name, root_path, updated_at FROM projects ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def recent_observations(self, project_key: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        sql = """
        SELECT o.id, p.project_key, o.type, o.title, o.summary, o.status, o.updated_at
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
        if project_key:
            where = "AND p.project_key = ?"
            params.append(project_key)
        params.append(limit)
        try:
            rows = self.conn.execute(
                f"""
                SELECT o.id, p.project_key, o.type, o.title, o.summary, o.status, o.updated_at,
                       bm25(observations_fts) AS rank
                FROM observations_fts
                JOIN observations o ON o.id = observations_fts.rowid
                JOIN projects p ON p.id = o.project_id
                WHERE observations_fts MATCH ? {where}
                ORDER BY rank, o.updated_at DESC
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
                SELECT o.id, p.project_key, o.type, o.title, o.summary, o.status, o.updated_at
                FROM observations o
                JOIN projects p ON p.id = o.project_id
                WHERE (o.title LIKE ? OR o.summary LIKE ? OR o.detail LIKE ?) {where}
                ORDER BY o.updated_at DESC
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

    def project_brief(self, project_key: str) -> dict[str, Any] | None:
        project = self.conn.execute(
            "SELECT id, project_key, name, root_path, updated_at FROM projects WHERE project_key = ?",
            (project_key,),
        ).fetchone()
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
        }

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
