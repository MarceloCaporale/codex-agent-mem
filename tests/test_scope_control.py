from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event
from codex_agent_mem.project_doc import sync_project_doc


def _ingest(store: CodexAgentMemStore, payload: dict) -> None:
    store.ingest_event(payload, normalize_event(payload))


def test_recent_changes_and_scope_guard_from_last_sync(tmp_path: Path):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    base = {
        "runtime": "codex",
        "project_key": "scope-demo",
        "session_id": "thread-1",
        "cwd": str(workdir),
        "metadata": {},
    }
    _ingest(
        store,
        {
            **base,
            "turn_id": "turn-1",
            "timestamp": "2026-04-17T00:00:00Z",
            "input_messages": [
                "Objective: preserve scope.\n"
                "Project DoD: keep closure deterministic.\n"
                "Mission DoD: expose mem_open_work and mem_completion_check.\n"
                "Session DoD: verify budget packs sync correctly.\n"
                "Constraint: keep ETAPA 10 closed.\n"
                "Pending: expose mem_open_work.\n"
                "Blocker: no human validation yet."
            ],
            "assistant_message": "Decision: keep sqlite local.\nStatus: complete",
        },
    )
    sync_result = sync_project_doc(store=store, project_key="scope-demo", cwd=workdir)
    if sync_result is None or sync_result["skipped"]:
        baseline_pack = store.context_pack("scope-demo", budget="normal")
        assert baseline_pack is not None
        store.record_context_sync(
            project_key="scope-demo",
            target_path=str(workdir / "AGENTS.md"),
            skipped=False,
            reason=None,
            stats=baseline_pack["stats"],
        )

    _ingest(
        store,
        {
            **base,
            "turn_id": "turn-2",
            "timestamp": "2026-04-17T00:10:00Z",
            "input_messages": [
                "Completed: expose mem_open_work.\n"
                "Pending: expose mem_completion_check.\n"
                "Pending: verify budget packs sync correctly.\n"
                "Blocker: human validation still missing."
            ],
            "assistant_message": (
                "Decision: use the micro pack when open work fits.\n"
                "Completed: expose mem_open_work.\n"
                "Pending: expose mem_completion_check.\n"
                "Status: complete"
            ),
        },
    )

    changes = store.recent_changes("scope-demo")
    assert changes is not None
    assert changes["baseline_source"] in {
        "last_successful_context_sync",
        "sync_before_latest_meaningful_change",
    }
    assert any(item["summary"] == "expose mem_completion_check." for item in changes["new_pending_items"])
    assert any(item["summary"] == "expose mem_open_work." for item in changes["resolved_pending_items"])
    assert changes["new_decisions"]
    guard = store.scope_guard("scope-demo")
    assert guard is not None
    assert guard["has_open_work"] is True
    assert "keep ETAPA 10 closed." in guard["must_not_drop"]
    assert "closure_mismatch" in guard["conflict_flags"]


def test_auto_budget_escalates_when_open_work_volume_grows(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    payload = {
        "runtime": "codex",
        "project_key": "budget-auto-demo",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": [
            "Objective: preserve the open work.\n"
            "Project DoD: keep closure deterministic.\n"
            "Mission DoD: expose mem_open_work and mem_completion_check.\n"
            "Session DoD: verify budget packs sync correctly.\n"
            "Pending: item one.\n"
            "Pending: item two.\n"
            "Pending: item three.\n"
            "Pending: item four.\n"
            "Blocker: blocker one.\n"
            "Blocker: blocker two.\n"
            "Blocker: blocker three.\n"
            "Constraint: keep scope narrow.\n"
            "Constraint: keep ETAPA 10 closed.\n"
            "Constraint: keep audit evidence explicit."
        ],
        "assistant_message": "Decision: preserve the compact pack.\nStatus: complete",
        "metadata": {},
    }
    _ingest(store, payload)
    pack = store.context_pack("budget-auto-demo", budget="auto")
    assert pack is not None
    assert pack["stats"]["budget"] in {"normal", "full"}
    assert pack["stats"]["budget_reason"] in {"fits_open_work_profile", "requires_full_profile"}
