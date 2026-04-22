import json
from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event
from codex_agent_mem.mcp_stdio import CodexAgentMemMCPServer, MCPRuntimeState


def seed(store: CodexAgentMemStore, cwd: str):
    raw_payload = {
        "runtime": "codex",
        "project_key": "demo-project",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": cwd,
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": [
            "Objective: stabilize auth continuity.\n"
            "Project DoD: keep closure deterministic.\n"
            "Mission DoD: expose mem_open_work and mem_completion_check.\n"
            "Session DoD: verify budget packs sync correctly.\n"
            "Pending: wire scope guard."
        ],
        "assistant_message": "Decision: Keep JWT auth for v1.\nPending: wire scope guard.",
        "metadata": {},
    }
    store.ingest_event(raw_payload, normalize_event(raw_payload))


def test_mcp_tools(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    workspace = tmp_path / "demo-project"
    workspace.mkdir()
    seed(store, str(workspace))
    server = CodexAgentMemMCPServer(store, MCPRuntimeState(db_path=tmp_path / "codex_agent_mem.db", idle_timeout_seconds=300))

    init = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "codex-agent-mem"

    tools = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "mem_search" in names
    assert "mem_open_work" in names
    assert "mem_completion_check" in names
    assert "mem_recent_changes" in names
    assert "mem_scope_guard" in names
    assert "mem_context_pack" in names
    assert "mem_provenance" in names
    assert "mem_health" in names
    assert "mem_health_runtime" in names
    assert "mem_snapshot_list" in names
    assert "mem_policy_list" in names
    assert "mem_policy_validate" in names
    assert "mem_inheritance_list" in names
    assert "mem_repair_propose" in names

    search = server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "mem_search", "arguments": {"query": "JWT", "project_key": "demo-project"}},
    })
    body = search["result"]["structuredContent"]
    assert isinstance(body, dict)
    assert body["count"] >= 1
    obs_id = body["items"][0]["id"]

    get_obs = server.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "mem_get", "arguments": {"observation_id": obs_id}},
    })
    assert get_obs["result"]["structuredContent"]["id"] == obs_id

    pack = server.handle_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "mem_context_pack", "arguments": {"project_key": "demo-project", "budget": "auto"}},
    })
    assert "Working Memory" in pack["result"]["structuredContent"]["text"]
    assert "Pending work" in pack["result"]["structuredContent"]["text"]
    assert pack["result"]["structuredContent"]["stats"]["budget"] in {"micro", "normal", "full"}
    open_work = server.handle_request({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "mem_open_work", "arguments": {"project_key": "demo-project"}},
    })
    assert open_work["result"]["structuredContent"]["has_open_work"] is True
    completion = server.handle_request({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "mem_completion_check", "arguments": {"project_key": "demo-project"}},
    })
    assert completion["result"]["structuredContent"]["done"] is False
    recent_changes = server.handle_request({
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {"name": "mem_recent_changes", "arguments": {"project_key": "demo-project"}},
    })
    assert "baseline_source" in recent_changes["result"]["structuredContent"]
    scope_guard = server.handle_request({
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {"name": "mem_scope_guard", "arguments": {"project_key": "demo-project"}},
    })
    assert scope_guard["result"]["structuredContent"]["must_not_drop"]
    provenance = server.handle_request({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": "mem_provenance", "arguments": {"observation_id": obs_id}},
    })
    assert provenance["result"]["structuredContent"]["memory_kind"] == "observation"
    health = server.handle_request({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "mem_health", "arguments": {"project_key": "demo-project"}},
    })
    assert "score" in health["result"]["structuredContent"]
    runtime_health = server.handle_request({
        "jsonrpc": "2.0",
        "id": 111,
        "method": "tools/call",
        "params": {"name": "mem_health_runtime", "arguments": {}},
    })
    assert runtime_health["result"]["structuredContent"]["connection_model"] == "one_process_per_connection"
    assert runtime_health["result"]["structuredContent"]["requests_count"] >= 1
    snapshot_create = server.handle_request({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {"name": "mem_snapshot_create", "arguments": {"project_key": "demo-project", "label": "mcp-checkpoint"}},
    })
    snapshot_id = snapshot_create["result"]["structuredContent"]["id"]
    snapshot_list = server.handle_request({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {"name": "mem_snapshot_list", "arguments": {"project_key": "demo-project"}},
    })
    assert snapshot_list["result"]["structuredContent"]["count"] >= 1
    snapshot_restore = server.handle_request({
        "jsonrpc": "2.0",
        "id": 14,
        "method": "tools/call",
        "params": {"name": "mem_snapshot_restore", "arguments": {"project_key": "demo-project", "snapshot_id": snapshot_id}},
    })
    assert snapshot_restore["result"]["structuredContent"]["snapshot_id"] == snapshot_id

    policy_validate = server.handle_request({
        "jsonrpc": "2.0",
        "id": 15,
        "method": "tools/call",
        "params": {
            "name": "mem_policy_validate",
            "arguments": {"policy_kind": "exclude_from_pack", "rule": {"selector": {"types": ["pending_item"]}}},
        },
    })
    assert policy_validate["result"]["structuredContent"]["valid"] is True

    policy_add = server.handle_request({
        "jsonrpc": "2.0",
        "id": 16,
        "method": "tools/call",
        "params": {
            "name": "mem_policy_add",
            "arguments": {
                "project_key": "demo-project",
                "policy_kind": "exclude_from_pack",
                "rule": {"selector": {"types": ["pending_item"], "text_contains": ["expose mem_open_work"]}},
            },
        },
    })
    policy_id = policy_add["result"]["structuredContent"]["id"]

    policy_list = server.handle_request({
        "jsonrpc": "2.0",
        "id": 17,
        "method": "tools/call",
        "params": {"name": "mem_policy_list", "arguments": {"project_key": "demo-project"}},
    })
    assert policy_list["result"]["structuredContent"]["count"] >= 1

    base_payload = {
        "runtime": "codex",
        "project_key": "base-project",
        "session_id": "base-thread",
        "turn_id": "base-turn",
        "cwd": str(workspace / "base"),
        "timestamp": "2026-04-17T00:02:00Z",
        "input_messages": ["Objective: share auth continuity.\nConstraint: keep sqlite local-first."],
        "assistant_message": "Decision: keep shared auth stable.",
    }
    store.ingest_event(base_payload, normalize_event(base_payload))
    server.handle_request({
        "jsonrpc": "2.0",
        "id": 18,
        "method": "tools/call",
        "params": {
            "name": "mem_policy_add",
            "arguments": {
                "project_key": "base-project",
                "policy_kind": "tag_as",
                "rule": {"selector": {"types": ["constraint"]}, "tag": "inheritable"},
            },
        },
    })
    inheritance_add = server.handle_request({
        "jsonrpc": "2.0",
        "id": 19,
        "method": "tools/call",
        "params": {
            "name": "mem_inheritance_add",
            "arguments": {
                "project_key": "demo-project",
                "source_project_key": "base-project",
                "mode": "combined",
                "selector": {"limit": 4},
            },
        },
    })
    inheritance_id = inheritance_add["result"]["structuredContent"]["id"]

    inheritance_list = server.handle_request({
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tools/call",
        "params": {"name": "mem_inheritance_list", "arguments": {"project_key": "demo-project"}},
    })
    assert inheritance_list["result"]["structuredContent"]["count"] >= 1

    repair_propose = server.handle_request({
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tools/call",
        "params": {"name": "mem_repair_propose", "arguments": {"project_key": "demo-project"}},
    })
    assert isinstance(repair_propose["result"]["structuredContent"]["items"], list)

    policy_remove = server.handle_request({
        "jsonrpc": "2.0",
        "id": 22,
        "method": "tools/call",
        "params": {"name": "mem_policy_remove", "arguments": {"project_key": "demo-project", "policy_id": policy_id}},
    })
    assert policy_remove["result"]["structuredContent"]["removed"] is True

    inheritance_remove = server.handle_request({
        "jsonrpc": "2.0",
        "id": 23,
        "method": "tools/call",
        "params": {"name": "mem_inheritance_remove", "arguments": {"project_key": "demo-project", "inheritance_id": inheritance_id}},
    })
    assert inheritance_remove["result"]["structuredContent"]["removed"] is True
    assert json.dumps(pack, ensure_ascii=True).isascii()
