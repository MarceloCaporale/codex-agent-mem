from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event


def _ingest(store: CodexAgentMemStore, payload: dict) -> None:
    store.ingest_event(payload, normalize_event(payload))


def test_policy_exclude_from_pack_and_inheritance(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")

    source_payload = {
        "runtime": "codex",
        "project_key": "base-project",
        "session_id": "base-thread",
        "turn_id": "base-turn-1",
        "cwd": str(tmp_path / "base"),
        "timestamp": "2026-04-18T00:00:00Z",
        "input_messages": [
            "Objective: stabilize shared auth.\n"
            "Constraint: keep sqlite local-first.\n"
            "Constraint: secret token ABC-123 must stay internal.\n"
            "Pending: preserve auth lineage."
        ],
        "assistant_message": (
            "Decision: keep auth shared across projects.\n"
            "Decision: Secret token ABC-123 should never enter packs."
        ),
    }
    target_payload = {
        "runtime": "codex",
        "project_key": "target-project",
        "session_id": "target-thread",
        "turn_id": "target-turn-1",
        "cwd": str(tmp_path / "target"),
        "timestamp": "2026-04-18T00:05:00Z",
        "input_messages": [
            "Objective: finish target continuity.\n"
            "Pending: temporary scaffolding cleanup.\n"
            "Pending: expose final dashboard."
        ],
        "assistant_message": "Decision: keep project focused.",
    }

    _ingest(store, source_payload)
    _ingest(store, target_payload)

    store.add_policy(
        "base-project",
        "tag_as",
        {"selector": {"types": ["constraint"]}, "tag": "inheritable"},
    )
    store.add_policy(
        "target-project",
        "exclude_from_pack",
        {"selector": {"text_contains": ["temporary scaffolding"]}},
    )
    store.add_policy(
        "target-project",
        "exclude_from_pack",
        {"selector": {"text_contains": ["ABC-123"]}},
    )
    store.add_inheritance(
        "target-project",
        "base-project",
        "combined",
        {"limit": 4},
    )

    pack = store.context_pack("target-project", budget="full")
    assert pack is not None
    assert "temporary scaffolding cleanup" not in pack["text"]
    assert "keep auth shared across projects" in pack["text"]
    assert "keep sqlite local-first" in pack["text"]
    assert "ABC-123" not in pack["text"]

    brief = store.project_brief("target-project")
    assert brief is not None
    assert any("inherited from base-project" in item["decision_text"] for item in brief["recent_decisions"])
    assert brief["inheritances"]
    assert brief["policies"]


def test_apply_duplicate_repair_reduces_effective_open_work(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    payload_1 = {
        "runtime": "codex",
        "project_key": "repair-project",
        "session_id": "repair-thread",
        "turn_id": "repair-turn-1",
        "cwd": str(tmp_path / "repair"),
        "timestamp": "2026-02-10T00:00:00Z",
        "input_messages": [
            "Objective: close review.\n"
            "Pending: verify final evidence.\n"
            "Pending: verify final evidence."
        ],
        "assistant_message": "Decision: keep review deterministic.",
    }
    payload_2 = {
        **payload_1,
        "turn_id": "repair-turn-2",
        "timestamp": "2026-02-11T00:00:00Z",
        "input_messages": ["Pending: verify final evidence."],
        "assistant_message": "Still pending.",
    }
    _ingest(store, payload_1)
    _ingest(store, payload_2)

    before_health = store.health_report("repair-project", record=True)
    assert before_health is not None
    assert before_health["duplicate_count"] >= 1

    before_recent = store.recent_observations("repair-project", limit=10)
    assert len(before_recent) >= 2

    before = store.open_work_report("repair-project")
    assert before is not None

    proposals = store._repair_proposals_from_health("repair-project")
    assert any(item["repair_kind"] == "archive_duplicate_observations" for item in proposals)

    applied = store.apply_repair("repair-project", "archive_duplicate_observations")
    assert applied["approved"] is True

    after_recent = store.recent_observations("repair-project", limit=10)
    assert len(after_recent) < len(before_recent)

    after_health = store.health_report("repair-project", record=False)
    assert after_health is not None
    assert after_health["duplicate_count"] < before_health["duplicate_count"]
