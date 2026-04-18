from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event


def test_ingest_persists_rows(tmp_path: Path):
    db_path = tmp_path / "codex_agent_mem.db"
    store = CodexAgentMemStore(db_path)
    raw_payload = {
        "runtime": "codex",
        "project_key": "demo-project",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": ["Please fix auth and keep JWT"],
        "assistant_message": "Decision: Keep JWT auth for v1.\nImplemented the summary.",
        "metadata": {"source": "test"},
    }
    event = normalize_event(raw_payload)
    result = store.ingest_event(raw_payload, event)
    assert result["ok"] is True
    assert result["inserted_turn"] is True
    assert len(result["observation_ids"]) >= 2

    projects = store.list_projects()
    assert projects[0]["project_key"] == "demo-project"

    recent = store.recent_observations(project_key="demo-project", limit=10)
    types = {row["type"] for row in recent}
    assert "session_summary" in types
    assert "decision" in types


def test_semicolon_separated_operational_labels_are_split(tmp_path: Path):
    db_path = tmp_path / "codex_agent_mem.db"
    store = CodexAgentMemStore(db_path)
    raw_payload = {
        "runtime": "codex",
        "project_key": "demo-project",
        "session_id": "thread-2",
        "turn_id": "turn-2",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-17T00:10:00Z",
        "input_messages": ["Objective: finish continuity; Pending: verify the pack before closing"],
        "assistant_message": "Objective: finish continuity; Pending: verify the pack before closing; Blocker: human validation pending",
        "metadata": {"source": "test"},
    }
    store.ingest_event(raw_payload, normalize_event(raw_payload))
    state = store.operational_state("demo-project")
    assert state is not None
    assert state["objective"]["summary"] == "finish continuity"
    assert state["pending_items"][0]["summary"] == "verify the pack before closing"
    assert state["blockers"][0]["summary"] == "human validation pending"
