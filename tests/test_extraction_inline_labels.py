from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event


def test_inline_labels_are_split_without_newlines(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    raw_payload = {
        "runtime": "codex",
        "project_key": "inline-labels",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": [
            "Objective: verify closure control. Project DoD: keep closure deterministic. "
            "Mission DoD: expose mem_open_work. Session DoD: verify budget packs. "
            "Pending: expose mem_open_work. Blocker: no human validation yet."
        ],
        "assistant_message": "Decision: use deterministic closure rules. Status: complete",
        "metadata": {},
    }
    store.ingest_event(raw_payload, normalize_event(raw_payload))
    state = store.operational_state("inline-labels")
    assert state is not None
    assert state["objective"]["summary"] == "verify closure control."
    assert len(state["dod"]["all_items"]) == 3
    assert len(state["dod"]["project_items"]) == 1
    assert len(state["dod"]["mission_items"]) == 1
    assert len(state["dod"]["session_items"]) == 1
    assert state["dod"]["project_items"][0]["summary"] == "keep closure deterministic."
    assert state["dod"]["mission_items"][0]["summary"] == "expose mem_open_work."
    assert state["dod"]["session_items"][0]["summary"] == "verify budget packs."
    assert state["pending_items"][0]["summary"] == "expose mem_open_work."
    assert state["blockers"][0]["summary"] == "no human validation yet."


def test_instruction_labels_do_not_create_noise_blockers(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    raw_payload = {
        "runtime": "codex",
        "project_key": "inline-noise",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-17T00:10:00Z",
        "input_messages": [
            "Pending: expose mem_completion_check. Blocker: human validation still missing. "
            "Respond with exactly five lines starting with Decision:, Completed:, Pending:, Blocker:, and Status: complete."
        ],
        "assistant_message": "Decision: keep closure deterministic. Status: complete",
        "metadata": {},
    }
    store.ingest_event(raw_payload, normalize_event(raw_payload))
    state = store.operational_state("inline-noise")
    assert state is not None
    assert len(state["blockers"]) == 1
    assert state["blockers"][0]["summary"] == "human validation still missing."
