from pathlib import Path

from fastapi.testclient import TestClient

from codex_agent_mem.api import create_app
from codex_agent_mem.config import AppConfig


def test_api_ingest_and_read(tmp_path: Path):
    app = create_app(AppConfig(db_path=tmp_path / "codex_agent_mem.db"))
    client = TestClient(app)

    payload = {
        "payload": {
            "type": "agent-turn-complete",
            "thread-id": "th-api",
            "turn-id": "tu-api",
            "cwd": str(tmp_path / "demo-repo"),
            "input-messages": ["Please lock auth storage"],
            "last-assistant-message": "Decision: keep sqlite for local memory",
            "timestamp": "2026-04-17T00:00:00Z",
        },
        "project_from_cwd": True,
    }

    ingest = client.post("/ingest/codex-notify", json=payload)
    assert ingest.status_code == 200
    body = ingest.json()
    assert body["ok"] is True

    recent = client.get("/recent", params={"project_key": "demo-repo"})
    assert recent.status_code == 200
    assert recent.json()["results"]

    brief = client.get("/projects/demo-repo/brief")
    assert brief.status_code == 200
    assert brief.json()["counts"]["observations"] >= 1

