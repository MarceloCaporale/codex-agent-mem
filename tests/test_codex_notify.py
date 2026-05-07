import json
import sqlite3
from pathlib import Path
from urllib import request

from codex_agent_mem.codex_notify import (
    codex_notify_to_generic,
    derive_project_identity,
    derive_project_key,
    ingest_direct,
    ingest_via_http,
)


def test_codex_notify_mapping():
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-1",
        "turn-id": "tu-1",
        "cwd": "/tmp/demo",
        "input-messages": ["hello"],
        "last-assistant-message": "Decision: use sqlite",
        "timestamp": "2026-04-17T00:00:00Z",
    }
    project_key = derive_project_key(payload, explicit=None, project_from_cwd=True)
    generic = codex_notify_to_generic(payload, project_key)
    assert generic["project_key"] == "demo"
    assert generic["session_id"] == "th-1"
    assert generic["turn_id"] == "tu-1"


def test_project_identity_prefers_mentioned_repo_over_broad_cwd(tmp_path: Path):
    workspace = tmp_path / "workspace"
    repo = workspace / "trip-studio"
    repo.mkdir(parents=True)
    (repo / "AGENTS.md").write_text("Scope: `trip-studio`\n", encoding="utf-8")
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-trip",
        "turn-id": "tu-trip",
        "cwd": str(workspace),
        "input-messages": [
            f"Implementa en el repo `{repo}` el frente TECNICO de v1.3_calidad_producto."
        ],
        "timestamp": "2026-04-29T00:00:00Z",
    }

    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)

    assert identity.project_key == "trip-studio"
    assert identity.root_path == str(repo)
    assert identity.source == "mentioned_path:AGENTS.md"
    assert identity.confidence == "high"


def test_project_identity_prefers_cwd_project_over_external_mentioned_path(tmp_path: Path):
    active_repo = tmp_path / "active-workspace"
    external_repo = tmp_path / "doors-api"
    active_repo.mkdir()
    external_repo.mkdir()
    (active_repo / "AGENTS.md").write_text("Scope: `active-workspace`\n", encoding="utf-8")
    (external_repo / "AGENTS.md").write_text("Scope: `doors-api`\n", encoding="utf-8")
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-office",
        "turn-id": "tu-office",
        "cwd": str(active_repo),
        "input-messages": [
            f"Verifica este proyecto y compara una nota externa en `{external_repo / 'AGENTS.md'}`."
        ],
        "timestamp": "2026-04-29T00:00:00Z",
    }

    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)

    assert identity.project_key == "active-workspace"
    assert identity.root_path == str(active_repo)
    assert identity.source == "cwd:AGENTS.md"
    assert "mentioned_path_ignored_due_to_cwd_project" in identity.warnings


def test_project_identity_payload_project_key_wins_over_cwd_and_mentions(tmp_path: Path):
    active_repo = tmp_path / "active"
    external_repo = tmp_path / "external"
    active_repo.mkdir()
    external_repo.mkdir()
    (active_repo / "AGENTS.md").write_text("Scope: `active-repo`\n", encoding="utf-8")
    (external_repo / "AGENTS.md").write_text("Scope: `external-repo`\n", encoding="utf-8")
    payload = {
        "project_key": "host-project-id",
        "cwd": str(active_repo),
        "input": f"Reference only: {external_repo}",
    }

    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)

    assert identity.project_key == "host-project-id"
    assert identity.source == "payload_project_key"


def test_project_identity_reads_generic_payload_text_fields(tmp_path: Path):
    workspace = tmp_path / "workspace"
    repo = workspace / "trip-studio"
    repo.mkdir(parents=True)
    (repo / "AGENTS.md").write_text("Scope: trip-studio\n", encoding="utf-8")
    payload = {
        "cwd": str(workspace),
        "input": f"Retomo el proyecto en {repo} despues de compactacion automatica.",
        "assistant_response": "Voy a completar health, smoke y Real Notes.",
    }

    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)

    assert identity.project_key == "trip-studio"
    assert identity.root_path == str(repo)
    assert identity.source == "mentioned_path:AGENTS.md"


def test_project_identity_uses_agents_scope_from_cwd(tmp_path: Path):
    repo = tmp_path / "trip-studio"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("Scope: trip-studio\n", encoding="utf-8")
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-trip",
        "turn-id": "tu-trip",
        "cwd": str(repo),
    }

    assert derive_project_key(payload, explicit=None, project_from_cwd=True) == "trip-studio"


def test_project_identity_ignores_generated_memory_scope_from_agents(tmp_path: Path):
    repo = tmp_path / "active-project"
    repo.mkdir()
    (repo / "AGENTS.md").write_text(
        """
# Project guidance

<!-- codex-agent-mem:generated-context:start -->
## codex-agent-mem Generated Context

Scope: `stale-project`

### Objective
- stale generated memory from a previous context
<!-- codex-agent-mem:generated-context:end -->
""",
        encoding="utf-8",
    )
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-active",
        "turn-id": "tu-active",
        "cwd": str(repo),
    }

    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)

    assert identity.project_key == "active-project"
    assert identity.root_path == str(repo)
    assert identity.source == "cwd:project_marker"


def test_project_identity_uses_project_state_canonical_name(tmp_path: Path):
    repo = tmp_path / "trip-studio"
    repo.mkdir()
    (repo / "PROJECTS_STATE_ts.md").write_text(
        "# PROJECTS_STATE_ts\n\nNombre canonico:\n\n- `trip-studio`\n",
        encoding="utf-8",
    )
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-trip",
        "turn-id": "tu-trip",
        "cwd": str(repo),
    }

    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)

    assert identity.project_key == "trip-studio"
    assert identity.source == "cwd:PROJECTS_STATE"


def test_project_identity_rejects_system32_as_project_key():
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-tech",
        "turn-id": "tu-tech",
        "cwd": r"C:\WINDOWS\System32",
    }

    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)

    assert identity.project_key == "default-project"
    assert identity.source == "fallback"
    assert "technical_cwd_ignored" in identity.warnings


def test_project_identity_does_not_use_mentioned_path_from_technical_cwd(tmp_path: Path):
    repo = tmp_path / "doors-api"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("Scope: `doors-api`\n", encoding="utf-8")
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-tech",
        "turn-id": "tu-tech",
        "cwd": r"C:\WINDOWS\System32",
        "input-messages": [f"Ambient prompt mentioned `{repo}` but this is not the active cwd."],
    }

    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)

    assert identity.project_key == "default-project"
    assert identity.source == "fallback"
    assert "technical_cwd_ignored" in identity.warnings


def test_direct_ingest_uses_resolved_project_root(tmp_path: Path):
    workspace = tmp_path / "workspace"
    repo = workspace / "trip-studio"
    repo.mkdir(parents=True)
    (repo / "AGENTS.md").write_text("Scope: `trip-studio`\n", encoding="utf-8")
    db_path = tmp_path / "codex_agent_mem.db"
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-trip",
        "turn-id": "tu-trip",
        "cwd": str(workspace),
        "input-messages": [f"Implementa en el repo `{repo}` el frente DATOS/API."],
        "last-assistant-message": "Pending: validate health and smoke.",
        "timestamp": "2026-04-29T00:00:00Z",
    }
    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)
    generic = codex_notify_to_generic(payload, identity.project_key, project_identity=identity)

    result = ingest_direct(db_path, payload, generic)

    assert result["project_key"] == "trip-studio"
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            "SELECT project_key, root_path FROM projects WHERE project_key = ?",
            ("trip-studio",),
        ).fetchone()
    assert row == ("trip-studio", str(repo))


def test_direct_ingest_keeps_active_cwd_project_when_prompt_mentions_external_repo(tmp_path: Path):
    active_repo = tmp_path / "active-workspace"
    external_repo = tmp_path / "doors-api"
    active_repo.mkdir()
    external_repo.mkdir()
    (active_repo / "AGENTS.md").write_text("Scope: `active-workspace`\n", encoding="utf-8")
    (external_repo / "AGENTS.md").write_text("Scope: `doors-api`\n", encoding="utf-8")
    db_path = tmp_path / "codex_agent_mem.db"
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-office",
        "turn-id": "tu-office",
        "cwd": str(active_repo),
        "input-messages": [f"Revisa IA; no cambies de proyecto aunque se mencione {external_repo}."],
        "last-assistant-message": "Decision: stay on the active workspace project.",
        "timestamp": "2026-04-29T00:00:00Z",
    }
    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)
    generic = codex_notify_to_generic(payload, identity.project_key, project_identity=identity)

    result = ingest_direct(db_path, payload, generic)

    assert result["project_key"] == "active-workspace"
    with sqlite3.connect(db_path) as con:
        rows = con.execute("SELECT project_key, root_path FROM projects ORDER BY project_key").fetchall()
    assert rows == [("active-workspace", str(active_repo))]


def test_direct_ingest_does_not_use_generated_memory_scope_as_project_identity(tmp_path: Path):
    repo = tmp_path / "active-project"
    repo.mkdir()
    (repo / "AGENTS.md").write_text(
        """
# Project guidance

<!-- codex-agent-mem:generated-context:start -->
## codex-agent-mem Generated Context

Scope: `stale-project`

### Objective
- stale generated memory from a previous context
<!-- codex-agent-mem:generated-context:end -->
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "codex_agent_mem.db"
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-active",
        "turn-id": "tu-active",
        "cwd": str(repo),
        "input-messages": ["Objective: register the active project start."],
        "last-assistant-message": "Decision: continue in active-project.",
        "timestamp": "2026-05-07T00:00:00Z",
    }
    identity = derive_project_identity(payload, explicit=None, project_from_cwd=True)
    generic = codex_notify_to_generic(payload, identity.project_key, project_identity=identity)

    result = ingest_direct(db_path, payload, generic)

    assert result["project_key"] == "active-project"
    with sqlite3.connect(db_path) as con:
        rows = con.execute("SELECT project_key, root_path FROM projects ORDER BY project_key").fetchall()
    assert rows == [("active-project", str(repo))]


def test_http_ingest_preserves_codex_contract(monkeypatch):
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "th-1",
        "turn-id": "tu-1",
        "cwd": "/tmp/demo",
    }
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"ok"

    def fake_urlopen(req: request.Request, timeout: int):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["timeout"] = timeout
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr("codex_agent_mem.codex_notify.request.urlopen", fake_urlopen)

    ingest_via_http("http://127.0.0.1:37770", payload, "demo-project", sync_project_doc_after_ingest=True)

    assert captured["url"] == "http://127.0.0.1:37770/ingest/codex-notify"
    assert captured["method"] == "POST"
    assert captured["timeout"] == 5
    assert captured["body"] == {
        "payload": payload,
        "project_key": "demo-project",
        "project_from_cwd": False,
        "sync_project_doc": True,
    }


def test_direct_ingest_can_sync_project_doc(tmp_path: Path):
    workdir = tmp_path / "demo-project"
    workdir.mkdir()
    db_path = tmp_path / "codex_agent_mem.db"
    payloads = [
            {
                "type": "agent-turn-complete",
                "thread-id": "th-1",
                "turn-id": "tu-1",
                "cwd": str(workdir),
                "input-messages": [
                    "Objective: keep billing continuity stable.\n"
                    "Constraint: keep ETAPA 10 closed.\n"
                    "Pending: write the audit note.\n"
                    "This repo needs a compact continuity layer that keeps the objective, the active scope, and the "
                    "remaining work available without replaying the whole history."
                ],
                "last-assistant-message": (
                    "Decision: keep sqlite for local auth memory.\n"
                    "Pending: write the audit note.\n"
                    "The stored continuity needs to preserve the working rules and the unfinished items for the next run."
                ),
                "timestamp": "2026-04-17T00:00:00Z",
            },
            {
                "type": "agent-turn-complete",
                "thread-id": "th-1",
                "turn-id": "tu-2",
                "cwd": str(workdir),
                "input-messages": [
                    "Pending: verify the context pack before closing.\n"
                    "We still need proof that the next run can resume from compact continuity instead of rebuilding "
                    "the full billing timeline."
                ],
                "last-assistant-message": (
                    "Decision: do not reopen ETAPA 10 scope inside this repo.\n"
                    "Completed: write the audit note.\n"
                    "Pending: verify the context pack before closing.\n"
                    "Do not announce completion while the verification step is still open."
                ),
                "timestamp": "2026-04-17T00:10:00Z",
            },
            {
                "type": "agent-turn-complete",
                "thread-id": "th-1",
                "turn-id": "tu-3",
                "cwd": str(workdir),
                "input-messages": [
                    "Summarize the continuity constraints for the next session.\n"
                    "The next run must remember the open verification item and the rule against false completion."
                ],
                "last-assistant-message": (
                    "Decision: resume from the latest matching item instead of reconstructing everything.\n"
                    "Status: complete\n"
                    "Future runs should carry forward the pending verification work even if the assistant claimed completion."
                ),
                "timestamp": "2026-04-17T00:20:00Z",
            },
    ]
    for payload in payloads[:-1]:
        generic = codex_notify_to_generic(payload, "demo-project")
        ingest_direct(
            db_path,
            payload,
            generic,
            sync_project_doc_after_ingest=False,
        )
    generic = codex_notify_to_generic(payloads[-1], "demo-project")
    result = ingest_direct(
        db_path,
        payloads[-1],
        generic,
        sync_project_doc_after_ingest=True,
    )
    assert result["ok"] is True
    assert result["project_doc_sync"]["skipped"] is False
    agents_path = workdir / "AGENTS.md"
    assert agents_path.exists()
    content = agents_path.read_text(encoding="utf-8")
    assert "codex-agent-mem Generated Context" in content
    assert "do not reopen ETAPA 10 scope" in content
    assert "Scope guard" in content
