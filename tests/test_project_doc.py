from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event
from codex_agent_mem.project_doc import choose_project_doc_path, sync_project_doc


def seed(store: CodexAgentMemStore, cwd: Path, project_key: str = "demo-project") -> None:
    payloads = [
        {
            "runtime": "codex",
            "project_key": project_key,
            "session_id": "thread-1",
            "turn_id": "turn-1",
            "cwd": str(cwd),
            "timestamp": "2026-04-17T00:00:00Z",
            "input_messages": [
                "Objective: finish the billing continuity patch.\n"
                "Constraint: do not reopen ETAPA 10 scope in this repo.\n"
                "Pending: write the billing audit note.\n"
                "This workspace needs a compact continuity layer that keeps the billing migration scoped, "
                "remembers the active deliverables, and avoids replaying the full previous discussion each time."
            ],
            "assistant_message": (
                "Decision: keep sqlite for local auth memory.\n"
                "Constraint: keep the migration path compact for future turns.\n"
                "Pending: write the billing audit note.\n"
                "The continuity block should preserve the operating rules, the remaining work, and the local-first "
                "recovery path so the next run does not reconstruct old context manually."
            ),
            "metadata": {},
        },
        {
            "runtime": "codex",
            "project_key": project_key,
            "session_id": "thread-1",
            "turn_id": "turn-2",
            "cwd": str(cwd),
            "timestamp": "2026-04-17T00:10:00Z",
            "input_messages": [
                "Pending: verify the context pack before closing.\n"
                "Blocker: no human validation yet.\n"
                "We still need to prove that the next run can resume from a compact state description instead of "
                "rehashing the entire billing migration history."
            ],
            "assistant_message": (
                "Decision: do not reopen ETAPA 10 scope inside this repo.\n"
                "Completed: write the billing audit note.\n"
                "Blocker: no human validation yet.\n"
                "The system must keep the active scope narrow and avoid announcing completion while validation "
                "and verification work are still pending."
            ),
            "metadata": {},
        },
        {
            "runtime": "codex",
            "project_key": project_key,
            "session_id": "thread-1",
            "turn_id": "turn-3",
            "cwd": str(cwd),
            "timestamp": "2026-04-17T00:20:00Z",
            "input_messages": [
                "Summarize the continuity constraints for the next session.\n"
                "The next run should know the objective, the remaining work, the blocker, and the rule that it "
                "must not close the task early."
            ],
            "assistant_message": (
                "Decision: preserve the compact migration plan and resume from the latest matching item.\n"
                "Pending: verify the context pack before closing.\n"
                "Status: complete\n"
                "The generated state should carry forward the open work and the blocker so future runs do not "
                "misread the task as already finished."
            ),
            "metadata": {},
        },
    ]
    for raw_payload in payloads:
        store.ingest_event(raw_payload, normalize_event(raw_payload))


def test_sync_project_doc_creates_agents_file(tmp_path: Path):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    seed(store, workdir)

    result = sync_project_doc(store=store, project_key="demo-project", cwd=workdir)

    assert result is not None
    assert result["skipped"] is False
    assert result["stats"]["approx_pack_tokens"] < result["stats"]["approx_source_tokens"]
    agents_path = workdir / "AGENTS.md"
    assert agents_path.exists()
    content = agents_path.read_text(encoding="utf-8")
    assert "Approx pack size" in content
    assert "Pending work" in content
    assert "Scope guard" in content
    assert "do not reopen ETAPA 10 scope" in content
    assert "verify the context pack before closing" in content
    state = store.operational_state("demo-project")
    assert state is not None
    assert state["objective"]["summary"] == "finish the billing continuity patch."
    assert state["pending_items"]
    assert state["blockers"]
    metrics = store.context_metrics_summary("demo-project")
    assert metrics is not None
    assert metrics["total_events"] >= 1
    assert metrics["synced_events"] >= 1


def test_sync_project_doc_prefers_override_file(tmp_path: Path):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    override_path = workdir / "AGENTS.override.md"
    override_path.write_text("# Local override\n", encoding="utf-8")
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    seed(store, workdir)

    result = sync_project_doc(store=store, project_key="demo-project", cwd=workdir)

    assert result is not None
    assert result["skipped"] is False
    assert result["path"] == str(override_path)
    assert choose_project_doc_path(workdir) == override_path
    content = override_path.read_text(encoding="utf-8")
    assert "codex-agent-mem Generated Context" in content
