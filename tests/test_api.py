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
            "input-messages": [
                "Objective: finish auth continuity.\n"
                "Project DoD: keep the closure check deterministic.\n"
                "Mission DoD: expose mem_open_work.\n"
                "Session DoD: wire the scope guard.\n"
                "Pending: wire the scope guard.\n"
                "Constraint: keep ETAPA 10 closed."
            ],
            "last-assistant-message": (
                "Decision: keep sqlite for local memory.\n"
                "Pending: wire the scope guard.\n"
                "Status: complete"
            ),
            "timestamp": "2026-04-17T00:00:00Z",
        },
        "project_from_cwd": True,
        "sync_project_doc": True,
    }


def test_api_ingest_and_read(tmp_path: Path):
    (tmp_path / "demo-repo").mkdir()
    app = create_app(AppConfig(db_path=tmp_path / "codex_agent_mem.db"))
    client = TestClient(app)

    ingest = client.post("/ingest/codex-notify", json=_payload(tmp_path))
    assert ingest.status_code == 200
    body = ingest.json()
    assert body["ok"] is True
    observation_id = body["observation_ids"][0]

    recent = client.get("/recent", params={"project_key": "demo-repo"})
    assert recent.status_code == 200
    assert recent.json()["results"]

    brief = client.get("/projects/demo-repo/brief")
    assert brief.status_code == 200
    assert brief.json()["counts"]["observations"] >= 1

    context_pack = client.get("/projects/demo-repo/context-pack", params={"budget": "auto"})
    assert context_pack.status_code == 200
    assert "Working Memory" in context_pack.json()["text"]
    assert "Pending work" in context_pack.json()["text"]
    assert context_pack.json()["stats"]["budget"] in {"micro", "normal", "full"}

    operational_state = client.get("/projects/demo-repo/operational-state")
    assert operational_state.status_code == 200
    assert operational_state.json()["pending_items"]
    assert operational_state.json()["dod"]["all_items"]

    open_work = client.get("/projects/demo-repo/open-work")
    assert open_work.status_code == 200
    assert open_work.json()["has_open_work"] is True

    completion_check = client.get("/projects/demo-repo/completion-check", params={"record": "true"})
    assert completion_check.status_code == 200
    assert completion_check.json()["done"] is False
    assert completion_check.json()["dod_missing_count"] >= 1

    recent_changes = client.get("/projects/demo-repo/recent-changes")
    assert recent_changes.status_code == 200
    assert "baseline_source" in recent_changes.json()

    scope_guard = client.get("/projects/demo-repo/scope-guard")
    assert scope_guard.status_code == 200
    assert scope_guard.json()["must_not_drop"]

    context_metrics = client.get("/projects/demo-repo/context-metrics")
    assert context_metrics.status_code == 200
    assert context_metrics.json()["total_events"] >= 1
    assert "budget_counts" in context_metrics.json()
    assert "avg_build_ms" in context_metrics.json()

    health = client.get("/projects/demo-repo/health")
    assert health.status_code == 200
    assert "score" in health.json()
    assert "suggestions" in health.json()

    health_recorded = client.get("/projects/demo-repo/health", params={"record": "true"})
    assert health_recorded.status_code == 200

    latest_health = client.get("/projects/demo-repo/health/latest")
    assert latest_health.status_code == 200
    assert latest_health.json()["score"] >= 0

    provenance = client.get(f"/observations/{observation_id}/provenance")
    assert provenance.status_code == 200
    assert provenance.json()["memory_kind"] == "observation"
    assert provenance.json()["source_turn"]["external_turn_id"] == "tu-api"

    snapshot_create = client.post("/projects/demo-repo/snapshots", json={"label": "api-checkpoint"})
    assert snapshot_create.status_code == 200
    snapshot_id = snapshot_create.json()["id"]

    snapshots = client.get("/projects/demo-repo/snapshots")
    assert snapshots.status_code == 200
    assert snapshots.json()["snapshots"]

    snapshot_restore = client.post(f"/projects/demo-repo/snapshots/{snapshot_id}/restore")
    assert snapshot_restore.status_code == 200
    assert "context_pack" in snapshot_restore.json()

    policy_validate = client.post(
        "/projects/demo-repo/policies/validate",
        json={
            "policy_kind": "exclude_from_pack",
            "rule": {"selector": {"types": ["pending_item"]}},
        },
    )
    assert policy_validate.status_code == 200
    assert policy_validate.json()["valid"] is True

    policy_create = client.post(
        "/projects/demo-repo/policies",
        json={
            "policy_kind": "exclude_from_pack",
            "rule": {"selector": {"types": ["pending_item"], "text_contains": ["finish auth continuity"]}},
        },
    )
    assert policy_create.status_code == 200
    policy_id = policy_create.json()["id"]

    policy_list = client.get("/projects/demo-repo/policies")
    assert policy_list.status_code == 200
    assert policy_list.json()["policies"]

    source_payload = {
        "runtime": "codex",
        "project_key": "base-source",
        "session_id": "base-thread",
        "turn_id": "base-turn",
        "cwd": str(tmp_path / "base-source"),
        "timestamp": "2026-04-17T00:02:00Z",
        "input_messages": [
            "Objective: share auth continuity.\nConstraint: keep sqlite local-first."
        ],
        "assistant_message": "Decision: keep shared auth stable.",
    }
    source_ingest = client.post("/ingest/generic", json={"payload": source_payload})
    assert source_ingest.status_code == 200
    source_tag_policy = client.post(
        "/projects/base-source/policies",
        json={
            "policy_kind": "tag_as",
            "rule": {"selector": {"types": ["constraint"]}, "tag": "inheritable"},
        },
    )
    assert source_tag_policy.status_code == 200
    inheritance_create = client.post(
        "/projects/demo-repo/inheritances",
        json={
            "source_project_key": "base-source",
            "mode": "combined",
            "selector": {"limit": 4},
        },
    )
    assert inheritance_create.status_code == 200
    inheritance_id = inheritance_create.json()["id"]

    inheritance_list = client.get("/projects/demo-repo/inheritances")
    assert inheritance_list.status_code == 200
    assert inheritance_list.json()["inheritances"]

    repairs = client.get("/projects/demo-repo/repairs")
    assert repairs.status_code == 200
    assert "proposals" in repairs.json()

    delete_policy = client.delete(f"/projects/demo-repo/policies/{policy_id}")
    assert delete_policy.status_code == 200
    assert delete_policy.json()["removed"] is True

    delete_inheritance = client.delete(f"/projects/demo-repo/inheritances/{inheritance_id}")
    assert delete_inheritance.status_code == 200
    assert delete_inheritance.json()["removed"] is True

    closure_metrics = client.get("/projects/demo-repo/closure-metrics")
    assert closure_metrics.status_code == 200
    assert closure_metrics.json()["total_events"] >= 1


def test_inspector_routes_render(tmp_path: Path):
    (tmp_path / "demo-repo").mkdir()
    app = create_app(AppConfig(db_path=tmp_path / "codex_agent_mem.db"))
    client = TestClient(app)

    ingest = client.post("/ingest/codex-notify", json=_payload(tmp_path))
    assert ingest.status_code == 200
    turn_id = ingest.json()["turn_row_id"]

    home = client.get("/ui")
    assert home.status_code == 200
    assert "Memory Inspector" in home.text
    assert "demo-repo" in home.text
    assert "Inspector" in home.text
    assert "Projects" in home.text
    assert "Sessions / Threads" in home.text
    assert "Recent Activity" in home.text
    assert "Recent" in home.text

    project = client.get("/ui/projects/demo-repo")
    assert project.status_code == 200
    assert "Project" in project.text
    assert "Selected turn" in project.text
    assert "Current Status" in project.text
    assert "Current Pack Savings" in project.text
    assert "Not ready to close" in project.text
    assert "Generated Working Memory" in project.text
    assert "Operational State" in project.text
    assert "Context Sync Metrics" in project.text
    assert "Closure Control" in project.text
    assert "Recent Changes" in project.text
    assert "Scope Guard" in project.text
    assert "Health" in project.text
    assert "Snapshots" in project.text
    assert "Selected Turn" in project.text
    assert "demo repo · 2026-04-17 00:00" in project.text
    assert "finish auth continuity" in project.text
    assert "Decision: keep sqlite for local memory" in project.text

    turn = client.get(f"/ui/turns/{turn_id}")
    assert turn.status_code == 200
    assert "Selected turn" in turn.text
    assert "Raw payload" in turn.text
    assert "Decision: keep sqlite for local memory" in turn.text

    observation = client.get("/ui/observations/1")
    assert observation.status_code == 200
    assert "Provenance" in observation.text
    assert "Source turn" in observation.text
