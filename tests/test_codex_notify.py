import json
from urllib import request

from codex_agent_mem.codex_notify import codex_notify_to_generic, derive_project_key, ingest_via_http


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

    ingest_via_http("http://127.0.0.1:37770", payload, "demo-project")

    assert captured["url"] == "http://127.0.0.1:37770/ingest/codex-notify"
    assert captured["method"] == "POST"
    assert captured["timeout"] == 5
    assert captured["body"] == {
        "payload": payload,
        "project_key": "demo-project",
        "project_from_cwd": False,
    }
