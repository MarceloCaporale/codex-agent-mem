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
            "input_messages": ["Keep auth local and simple while preserving previous migration rules."],
            "assistant_message": (
                "Decision: keep sqlite for local auth memory.\n"
                "We should avoid network-only state and keep the migration path compact for future turns."
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
            "input_messages": ["Do not reopen ETAPA 10 scope in this repo. Focus on billing migration continuity."],
            "assistant_message": (
                "Decision: do not reopen ETAPA 10 scope inside this repo.\n"
                "Continue the billing migration and preserve the local sqlite cache of record."
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
            "input_messages": ["Summarize the continuity constraints for the next session."],
            "assistant_message": (
                "Decision: preserve the compact migration plan and resume from the latest matching item.\n"
                "Do not reconstruct old context from scratch when the stored continuity block already covers it."
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
    assert (
        "do not reopen ETAPA 10 scope" in content
        or "keep sqlite for local auth memory" in content
        or "preserve the compact migration plan" in content
    )


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
