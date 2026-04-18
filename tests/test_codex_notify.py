import json
from pathlib import Path
from urllib import request

from codex_agent_mem.codex_notify import codex_notify_to_generic, derive_project_key, ingest_direct, ingest_via_http


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
                "input-messages": ["Keep auth local and simple while preserving migration continuity, previous rollout constraints, and the local-only recovery path for billing work."],
                "last-assistant-message": "Decision: keep sqlite for local auth memory.\nPreserve the local recovery path, avoid reconstructing old billing context manually, and keep continuity constraints explicit.",
                "timestamp": "2026-04-17T00:00:00Z",
            },
            {
                "type": "agent-turn-complete",
                "thread-id": "th-1",
                "turn-id": "tu-2",
                "cwd": str(workdir),
                "input-messages": ["Do not reopen ETAPA 10 scope in this repo, and keep the migration narrowed to the billing continuity problem rather than expanding to new architectural work."],
                "last-assistant-message": "Decision: do not reopen ETAPA 10 scope inside this repo.\nStay on the billing continuity problem and keep the migration narrowed to local memory and resumability.",
                "timestamp": "2026-04-17T00:10:00Z",
            },
            {
                "type": "agent-turn-complete",
                "thread-id": "th-1",
                "turn-id": "tu-3",
                "cwd": str(workdir),
                "input-messages": ["Summarize the continuity constraints for the next session so the next run can resume without replaying the whole previous conversation or the full migration history."],
                "last-assistant-message": "Decision: resume from the latest matching item instead of reconstructing everything.\nUse the generated continuity block first, and only fall back to older memory retrieval when the stored pack is not enough.",
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
