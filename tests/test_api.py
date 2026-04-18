from pathlib import Path

from fastapi.testclient import TestClient

from codex_agent_mem.api import create_app
from codex_agent_mem.config import AppConfig


def _payload(tmp_path: Path) -> dict:
    return {
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


def test_api_ingest_and_read(tmp_path: Path):
    app = create_app(AppConfig(db_path=tmp_path / "codex_agent_mem.db"))
    client = TestClient(app)

    ingest = client.post("/ingest/codex-notify", json=_payload(tmp_path))
    assert ingest.status_code == 200
    body = ingest.json()
    assert body["ok"] is True

    recent = client.get("/recent", params={"project_key": "demo-repo"})
    assert recent.status_code == 200
    assert recent.json()["results"]

    brief = client.get("/projects/demo-repo/brief")
    assert brief.status_code == 200
    assert brief.json()["counts"]["observations"] >= 1

    context_pack = client.get("/projects/demo-repo/context-pack")
    assert context_pack.status_code == 200
    assert "Working Memory" in context_pack.json()["text"]


def test_inspector_routes_render(tmp_path: Path):
    app = create_app(AppConfig(db_path=tmp_path / "codex_agent_mem.db"))
    client = TestClient(app)

    ingest = client.post("/ingest/codex-notify", json=_payload(tmp_path))
    assert ingest.status_code == 200
    turn_id = ingest.json()["turn_row_id"]

    home = client.get("/ui")
    assert home.status_code == 200
    assert "Memory Inspector" in home.text
    assert "demo-repo" in home.text

    project = client.get("/ui/projects/demo-repo")
    assert project.status_code == 200
    assert "Generated Working Memory" in project.text
    assert "Selected Turn" in project.text
    assert "demo repo · 2026-04-17 00:00" in project.text
    assert "Please lock auth storage" in project.text
    assert "Decision: keep sqlite for local memory" in project.text

    turn = client.get(f"/ui/turns/{turn_id}")
    assert turn.status_code == 200
    assert "Raw payload" in turn.text
    assert "Decision: keep sqlite for local memory" in turn.text
