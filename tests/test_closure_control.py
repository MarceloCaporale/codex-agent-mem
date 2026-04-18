from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event


def _ingest(store: CodexAgentMemStore, payload: dict) -> None:
    store.ingest_event(payload, normalize_event(payload))


def test_hierarchical_dod_and_completion_check(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    base = {
        "runtime": "codex",
        "project_key": "closure-demo",
        "session_id": "thread-1",
        "cwd": str(tmp_path),
        "metadata": {},
    }
    _ingest(
        store,
        {
            **base,
            "turn_id": "turn-1",
            "timestamp": "2026-04-17T00:00:00Z",
            "input_messages": [
                "Objective: close the audit slice.\n"
                "Project DoD: keep the closure check deterministic.\n"
                "Mission DoD: expose mem_open_work and mem_completion_check.\n"
                "Session DoD: prove the pack budgets work.\n"
                "Pending: expose mem_open_work."
            ],
            "assistant_message": (
                "Decision: use deterministic closure rules.\n"
                "Completed: keep the closure check deterministic.\n"
                "Status: complete"
            ),
        },
    )

    state = store.operational_state("closure-demo")
    assert state is not None
    assert len(state["dod"]["all_items"]) == 3
    assert len(state["dod"]["project_items"]) == 1
    assert len(state["dod"]["mission_items"]) == 1
    assert len(state["dod"]["session_items"]) == 1
    assert len(state["dod_missing"]["all_items"]) == 2

    open_work = store.open_work_report("closure-demo")
    assert open_work is not None
    assert open_work["has_open_work"] is True
    assert open_work["dod_missing"]

    completion = store.completion_check("closure-demo")
    assert completion is not None
    assert completion["done"] is False
    assert "pending_items_open" in completion["reasons"]
    assert "dod_incomplete" in completion["reasons"]
    assert completion["closure_mismatch"] is True

    metrics = store.closure_metrics_summary("closure-demo")
    assert metrics is not None
    assert metrics["mismatch_events"] >= 1


def test_context_pack_budgets_shrink_in_order(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    payload = {
        "runtime": "codex",
        "project_key": "budget-demo",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": [
            "Objective: preserve the active scope.\n"
            "Project DoD: expose deterministic closure checks.\n"
            "Mission DoD: keep the context pack compact.\n"
            "Session DoD: verify the generated AGENTS block.\n"
            "Constraint: do not silently narrow the task.\n"
            "Pending: verify the compact pack.\n"
            "Pending: expose mem_open_work.\n"
            "Blocker: human validation missing."
        ],
        "assistant_message": (
            "Decision: carry open work forward in the generated pack.\n"
            "Decision: use MCP only for older detail.\n"
            "Completed: expose deterministic closure checks.\n"
            "Pending: verify the compact pack.\n"
            "Blocker: human validation missing."
        ),
        "metadata": {},
    }
    _ingest(store, payload)

    micro = store.context_pack("budget-demo", budget="micro")
    normal = store.context_pack("budget-demo", budget="normal")
    full = store.context_pack("budget-demo", budget="full")

    assert micro is not None and normal is not None and full is not None
    assert micro["stats"]["budget"] == "micro"
    assert normal["stats"]["budget"] == "normal"
    assert full["stats"]["budget"] == "full"
    assert micro["stats"]["pack_char_count"] <= normal["stats"]["pack_char_count"] <= full["stats"]["pack_char_count"]
    assert "Definition of Done gaps" in normal["text"]
    assert "Pending work" in micro["text"]


def test_near_duplicate_blockers_are_deduped(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    payload = {
        "runtime": "codex",
        "project_key": "dedupe-demo",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": [
            "Blocker: human validation still missing. "
            "Pending: expose mem_completion_check."
        ],
        "assistant_message": (
            "Blocker: Human validation is still missing.\n"
            "Pending: Expose `mem_completion_check`.\n"
            "Status: complete"
        ),
        "metadata": {},
    }
    _ingest(store, payload)
    completion = store.completion_check("dedupe-demo")
    assert completion is not None
    assert completion["blocker_count"] == 1


def test_no_human_validation_yet_and_missing_are_deduped(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    payload = {
        "runtime": "codex",
        "project_key": "dedupe-demo-2",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": [
            "Blocker: no human validation yet. Pending: expose mem_open_work."
        ],
        "assistant_message": (
            "Blocker: human validation still missing.\n"
            "Pending: expose mem_open_work.\n"
            "Status: complete"
        ),
        "metadata": {},
    }
    _ingest(store, payload)
    completion = store.completion_check("dedupe-demo-2")
    assert completion is not None
    assert completion["blocker_count"] == 1
