from pathlib import Path

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event
from codex_agent_mem.mcp_stdio import CodexAgentMemMCPServer


def seed(store: CodexAgentMemStore):
    raw_payload = {
        "runtime": "codex",
        "project_key": "demo-project",
        "session_id": "thread-1",
        "turn_id": "turn-1",
        "cwd": "/tmp/demo",
        "timestamp": "2026-04-17T00:00:00Z",
        "input_messages": ["Audit auth choices"],
        "assistant_message": "Decision: Keep JWT auth for v1.\nWe should preserve compatibility.",
        "metadata": {},
    }
    store.ingest_event(raw_payload, normalize_event(raw_payload))


def test_mcp_tools(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    seed(store)
    server = CodexAgentMemMCPServer(store)

    init = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "codex-agent-mem"

    tools = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "mem_search" in names
    assert "mem_context_pack" in names

    search = server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "mem_search", "arguments": {"query": "JWT", "project_key": "demo-project"}},
    })
    body = search["result"]["structuredContent"]
    assert body
    obs_id = body[0]["id"]

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
        "params": {"name": "mem_context_pack", "arguments": {"project_key": "demo-project"}},
    })
    assert "Working Memory" in pack["result"]["structuredContent"]["text"]
