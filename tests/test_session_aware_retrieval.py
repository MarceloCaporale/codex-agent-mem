from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from codex_agent_mem.db import CodexAgentMemStore
from codex_agent_mem.ingest import normalize_event
from codex_agent_mem.mcp_stdio import CodexAgentMemMCPServer, MCPRuntimeState
from codex_agent_mem.models import Observation
from codex_agent_mem.runtime_efficiency import compact_text_summary


def _ingest_lane(
    store: CodexAgentMemStore,
    tmp_path: Path,
    lane: str,
    timestamp: str,
    *,
    project_key: str = "session-aware-demo",
    cwd: Path | None = None,
) -> None:
    raw_payload = {
        "runtime": "codex",
        "project_key": project_key,
        "session_id": f"{lane}-thread",
        "turn_id": f"{lane}-turn-1",
        "cwd": str(cwd or tmp_path),
        "timestamp": timestamp,
        "input_messages": [
            f"Objective: keep {lane} release lane isolated.\n"
            f"Pending: verify {lane} scoped context pack."
        ],
        "assistant_message": (
            f"Decision: {lane} lane owns its own continuity.\n"
            f"Pending: finish {lane} scoped MCP smoke."
        ),
        "metadata": {"source": "session-aware-test"},
    }
    store.ingest_event(raw_payload, normalize_event(raw_payload))


def _session_id_by_external(
    store: CodexAgentMemStore,
    external_session_id: str,
    *,
    project_key: str = "session-aware-demo",
) -> int:
    sessions = store.list_sessions(project_key)
    matches = [item for item in sessions if item["external_session_id"] == external_session_id]
    assert matches
    return int(matches[0]["id"])


def _insert_observation(
    store: CodexAgentMemStore,
    tmp_path: Path,
    *,
    project_key: str,
    external_session_id: str,
    external_turn_id: str,
    timestamp: str,
    summary: str,
    obs_type: str = "user_request",
    status: str = "active",
) -> None:
    raw_payload = {
        "runtime": "codex",
        "project_key": project_key,
        "session_id": external_session_id,
        "turn_id": external_turn_id,
        "cwd": str(tmp_path),
        "timestamp": timestamp,
        "input_messages": [summary],
        "assistant_message": "",
        "metadata": {"source": "session-aware-test"},
    }
    event = normalize_event(raw_payload)
    project_id = store.upsert_project(project_key, str(tmp_path))
    session_id = store.upsert_session(project_id, event)
    turn_id, _inserted = store.upsert_turn(session_id, raw_payload, event)
    store.upsert_observation(
        project_id,
        session_id,
        turn_id,
        event,
        Observation(
            type=obs_type,
            title=f"{obs_type}: {summary[:40]}",
            summary=summary,
            detail=summary,
            status=status,
        ),
    )


def test_context_pack_can_be_scoped_to_one_session(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z")
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z")

    alpha_session_id = _session_id_by_external(store, "alpha-thread")
    sessions = store.list_sessions("session-aware-demo")
    assert {item["external_session_id"] for item in sessions} == {"alpha-thread", "beta-thread"}

    global_pack = store.context_pack("session-aware-demo", budget="full")
    assert global_pack is not None
    assert global_pack["stats"]["session_filter_applied"] is False
    assert global_pack["stats"]["source_session_count"] == 2
    assert global_pack["stats"]["multiple_sessions_detected"] is True
    assert global_pack["stats"]["scope_warning"]["code"] == "multi_session_project_scope"
    assert global_pack["stats"]["active_objective_uncertain"] is True
    assert global_pack["stats"]["active_objective_suppressed"] is True
    assert global_pack["stats"]["live_turn_awareness"] is False
    assert {item["external_session_id"] for item in global_pack["stats"]["source_sessions"]} == {
        "alpha-thread",
        "beta-thread",
    }
    assert "Scope warning:" in global_pack["text"]
    assert "Suggested narrowing:" in global_pack["text"]
    assert "Objective (project-wide candidate)" not in global_pack["text"]
    assert "No active objective selected" in global_pack["text"]
    assert "not live current-turn awareness" in global_pack["text"]

    alpha_pack = store.context_pack("session-aware-demo", budget="full", session_id=alpha_session_id)
    assert alpha_pack is not None
    assert alpha_pack["stats"]["session_filter_applied"] is True
    assert alpha_pack["stats"]["source_session_count"] == 1
    assert alpha_pack["stats"]["scope_warning"] is None
    assert "recommended_narrowing" not in alpha_pack["stats"]
    assert alpha_pack["stats"]["live_turn_awareness"] is False
    assert alpha_pack["stats"]["source_sessions"][0]["external_session_id"] == "alpha-thread"
    assert alpha_pack["stats"]["source_sessions"][0]["last_turn_at"] == "2026-04-27T00:00:00Z"
    assert "session_filter=applied" in alpha_pack["text"]
    assert "Suggested narrowing:" not in alpha_pack["text"]
    assert "alpha" in alpha_pack["text"]
    assert "beta" not in alpha_pack["text"]

    alpha_open_work = store.open_work_report("session-aware-demo", session_id=alpha_session_id)
    assert alpha_open_work is not None
    pending_text = " ".join(item["summary"] for item in alpha_open_work["pending_items"])
    assert "alpha" in pending_text
    assert "beta" not in pending_text

    alpha_recent = store.recent_observations("session-aware-demo", session_id=alpha_session_id)
    assert alpha_recent
    assert {item["session_id"] for item in alpha_recent} == {alpha_session_id}

    alpha_brief = store.project_brief("session-aware-demo", session_id=alpha_session_id)
    assert alpha_brief is not None
    assert alpha_brief["session_filter"]["external_session_id"] == "alpha-thread"

    alpha_completion = store.completion_check("session-aware-demo", session_id=alpha_session_id)
    assert alpha_completion is not None
    assert alpha_completion["session_filter"]["external_session_id"] == "alpha-thread"

    alpha_scope_guard = store.scope_guard("session-aware-demo", session_id=alpha_session_id)
    assert alpha_scope_guard is not None
    assert alpha_scope_guard["session_filter"]["external_session_id"] == "alpha-thread"


def test_project_wide_pack_warns_when_multiple_sessions_share_one_lane(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    shared_cwd = tmp_path / "alpha-project"
    shared_cwd.mkdir()
    for external_session_id, timestamp in (
        ("alpha-one-thread", "2026-04-27T00:00:00Z"),
        ("alpha-two-thread", "2026-04-27T00:01:00Z"),
    ):
        raw_payload = {
            "runtime": "codex",
            "project_key": "session-aware-demo",
            "session_id": external_session_id,
            "turn_id": f"{external_session_id}-turn",
            "cwd": str(shared_cwd),
            "timestamp": timestamp,
            "input_messages": ["Objective: continue alpha-project release closure."],
            "assistant_message": "",
            "metadata": {"source": "session-aware-test"},
        }
        event = normalize_event(raw_payload)
        project_id = store.upsert_project("session-aware-demo", str(tmp_path))
        session_id = store.upsert_session(project_id, event)
        turn_id, _inserted = store.upsert_turn(session_id, raw_payload, event)
        store.upsert_observation(
            project_id,
            session_id,
            turn_id,
            event,
            Observation(
                type="pending_item",
                title="pending_item: alpha-project release closure",
                summary="alpha-project release closure remains active.",
                detail="alpha-project release closure remains active.",
                status="active",
            ),
        )

    resolution = store.scope_resolve("session-aware-demo")
    assert resolution is not None
    assert resolution["routing_decision"] == "needs_hint"
    assert resolution["multiple_sessions_detected"] is True
    assert resolution["multiple_lanes_detected"] is False
    assert resolution["do_not_fetch_project_wide_pack"] is True

    bootstrap = store.bootstrap_context("session-aware-demo", budget="micro")
    assert bootstrap is not None
    assert bootstrap["selection_mode"] == "needs_narrowing"
    assert bootstrap["context_pack"] is None
    assert bootstrap["scope_resolution"]["multiple_sessions_detected"] is True

    pack = store.context_pack("session-aware-demo", budget="micro")
    assert pack is not None
    assert pack["stats"]["source_session_count"] == 2
    assert pack["stats"]["multiple_sessions_detected"] is True
    assert pack["stats"]["multiple_lanes_detected"] is False
    assert pack["stats"]["broad_scope_detected"] is True
    assert pack["stats"]["do_not_fetch_project_wide_pack"] is True
    assert pack["stats"]["scope_warning"]["code"] == "multi_session_project_scope"


def test_scope_resolve_without_hint_does_not_pick_first_lane(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    alpha_cwd = tmp_path / "alpha-project"
    beta_cwd = tmp_path / "beta-project"
    alpha_cwd.mkdir()
    beta_cwd.mkdir()
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", cwd=alpha_cwd)
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", cwd=beta_cwd)

    resolution = store.scope_resolve("session-aware-demo")

    assert resolution is not None
    assert resolution["routing_decision"] == "needs_hint"
    assert resolution["recommended_scope"] is None
    assert resolution["do_not_fetch_project_wide_pack"] is True
    assert set(resolution["candidate_sub_scopes"]) == {"alpha-project", "beta-project"}
    assert resolution["recommended_call"] == 'mem_session_list(project_key, query="<target sub-scope>")'


def test_bootstrap_context_without_hint_blocks_broad_container_pack(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    alpha_cwd = tmp_path / "alpha-project"
    beta_cwd = tmp_path / "beta-project"
    alpha_cwd.mkdir()
    beta_cwd.mkdir()
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", cwd=alpha_cwd)
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", cwd=beta_cwd)

    bootstrap = store.bootstrap_context("session-aware-demo", budget="full")

    assert bootstrap is not None
    assert bootstrap["selection_mode"] == "needs_narrowing"
    assert bootstrap["session_id"] is None
    assert bootstrap["context_pack"] is None
    assert bootstrap["scope_resolution"]["do_not_fetch_project_wide_pack"] is True
    assert set(bootstrap["scope_resolution"]["candidate_sub_scopes"]) == {"alpha-project", "beta-project"}


def test_bootstrap_context_chat_title_resolves_lane_without_loading_project_pack(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    alpha_cwd = tmp_path / "alpha-project"
    beta_cwd = tmp_path / "beta-project"
    alpha_cwd.mkdir()
    beta_cwd.mkdir()
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", cwd=alpha_cwd)
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", cwd=beta_cwd)

    bootstrap = store.bootstrap_context(
        "session-aware-demo",
        chat_title="Retomar alpha-project",
        budget="full",
    )

    assert bootstrap is not None
    assert bootstrap["selection_mode"] == "lane_needs_session_selection"
    assert bootstrap["session_id"] is None
    assert bootstrap["context_pack"] is None
    resolution = bootstrap["scope_resolution"]
    assert resolution["routing_decision"] == "lane_resolved"
    assert resolution["recommended_scope"]["inferred_sub_scope"] == "alpha-project"
    assert "session_id" not in resolution["recommended_scope"]
    assert "external_session_id" not in resolution["recommended_scope"]
    assert set(resolution["candidate_sub_scopes"]) == {"alpha-project", "beta-project"}
    assert resolution["recommended_call"] == 'mem_session_list(project_key, query="alpha-project")'
    assert resolution["do_not_fetch_project_wide_pack"] is True


def test_bootstrap_context_exact_external_session_id_still_requires_explicit_session_id(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    alpha_cwd = tmp_path / "alpha-project"
    beta_cwd = tmp_path / "beta-project"
    alpha_cwd.mkdir()
    beta_cwd.mkdir()
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", cwd=alpha_cwd)
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", cwd=beta_cwd)

    bootstrap = store.bootstrap_context(
        "session-aware-demo",
        thread_hint="alpha-thread",
        budget="full",
    )

    assert bootstrap is not None
    assert bootstrap["selection_mode"] == "lane_needs_session_selection"
    assert bootstrap["session_id"] is None
    assert bootstrap["context_pack"] is None
    assert bootstrap["scope_resolution"]["recommended_scope"]["inferred_sub_scope"] == "alpha-project"
    assert "session_id" not in bootstrap["scope_resolution"]["recommended_scope"]
    assert bootstrap["recommended_call"] == 'mem_session_list(project_key, query="alpha-project")'


def test_bootstrap_context_explicit_session_id_returns_scoped_pack(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    alpha_cwd = tmp_path / "alpha-project"
    beta_cwd = tmp_path / "beta-project"
    alpha_cwd.mkdir()
    beta_cwd.mkdir()
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", cwd=alpha_cwd)
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", cwd=beta_cwd)
    alpha_session_id = _session_id_by_external(store, "alpha-thread")

    bootstrap = store.bootstrap_context(
        "session-aware-demo",
        session_id=alpha_session_id,
        budget="full",
    )

    assert bootstrap is not None
    assert bootstrap["selection_mode"] == "explicit_session_id"
    assert bootstrap["session_id"] == alpha_session_id
    assert bootstrap["context_pack"]["stats"]["session_filter_applied"] is True
    assert bootstrap["context_pack"]["stats"]["source_sessions"][0]["external_session_id"] == "alpha-thread"
    assert "alpha" in bootstrap["context_pack"]["text"]
    assert "beta" not in bootstrap["context_pack"]["text"]


def test_scope_guard_project_wide_exposes_lane_inventory(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    alpha_cwd = tmp_path / "alpha-project"
    beta_cwd = tmp_path / "beta-project"
    alpha_cwd.mkdir()
    beta_cwd.mkdir()
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", cwd=alpha_cwd)
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", cwd=beta_cwd)

    guard = store.scope_guard("session-aware-demo")

    assert guard is not None
    assert guard["session_filter_applied"] is False
    assert guard["multiple_lanes_detected"] is True
    assert guard["do_not_fetch_project_wide_pack"] is True
    assert guard["active_objective_suppressed"] is True
    assert guard["live_turn_awareness"] is False
    assert set(guard["candidate_sub_scopes"]) == {"alpha-project", "beta-project"}
    assert guard["recommended_narrowing"]["next_steps"][0]["arguments"]["query"] == "<target sub-scope>"


def test_project_wide_retrieval_filters_sessions_outside_project_root(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    active_repo = tmp_path / "IA_OFICINA_v5"
    external_cwd = tmp_path / "external-tools"
    active_repo.mkdir()
    external_cwd.mkdir()

    good_raw = {
        "runtime": "codex",
        "project_key": "IA_OFICINA_v5",
        "session_id": "office-thread",
        "turn_id": "office-turn",
        "cwd": str(active_repo),
        "timestamp": "2026-04-27T00:00:00Z",
        "input_messages": ["Objective: verify IA_OFICINA_v5 release closure."],
        "assistant_message": "Pending: finish IA_OFICINA_v5 local checks.",
        "metadata": {"project_root_path": str(active_repo), "project_resolution_source": "cwd:AGENTS.md"},
    }
    bad_raw = {
        "runtime": "codex",
        "project_key": "IA_OFICINA_v5",
        "session_id": "doors-thread",
        "turn_id": "doors-turn",
        "cwd": str(external_cwd),
        "timestamp": "2026-04-27T00:01:00Z",
        "input_messages": ["Objective: investigate doors-api reusable browser runtime."],
        "assistant_message": "Pending: continue doors-api extraction.",
        "metadata": {
            "project_root_path": str(active_repo),
            "project_resolution_source": "mentioned_path:AGENTS.md",
        },
    }
    store.ingest_event(good_raw, normalize_event(good_raw))
    store.ingest_event(bad_raw, normalize_event(bad_raw))

    pack = store.context_pack("IA_OFICINA_v5", budget="full")

    assert pack is not None
    assert "IA_OFICINA_v5 release closure" in pack["text"]
    assert "doors-api" not in pack["text"]
    assert pack["stats"]["source_session_count"] == 1
    assert pack["stats"]["source_sessions"][0]["external_session_id"] == "office-thread"

    search_results = store.search_observations("doors-api", project_key="IA_OFICINA_v5", limit=5)
    assert search_results == []

    doors_session_id = _session_id_by_external(
        store,
        "doors-thread",
        project_key="IA_OFICINA_v5",
    )
    scoped_pack = store.context_pack("IA_OFICINA_v5", budget="full", session_id=doors_session_id)
    assert scoped_pack is not None
    assert "doors-api" in scoped_pack["text"]
    assert scoped_pack["stats"]["source_sessions"][0]["external_session_id"] == "doors-thread"


def test_mcp_exposes_sessions_and_session_filtered_reads(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    alpha_cwd = tmp_path / "alpha-project"
    beta_cwd = tmp_path / "beta-project"
    alpha_cwd.mkdir()
    beta_cwd.mkdir()
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", cwd=alpha_cwd)
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", cwd=beta_cwd)
    alpha_session_id = _session_id_by_external(store, "alpha-thread")
    server = CodexAgentMemMCPServer(
        store,
        MCPRuntimeState(db_path=tmp_path / "codex_agent_mem.db", idle_timeout_seconds=300),
    )

    tools = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert "mem_session_list" in names
    assert "mem_scope_resolve" in names
    assert "mem_bootstrap_context" in names

    session_list = server.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "mem_session_list", "arguments": {"project_key": "session-aware-demo"}},
    })
    assert session_list["result"]["structuredContent"]["count"] == 2
    assert "items" in session_list["result"]["structuredContent"]
    assert [item["external_session_id"] for item in session_list["result"]["structuredContent"]["items"]] == [
        "beta-thread",
        "alpha-thread",
    ]

    limited_session_list = server.handle_request({
        "jsonrpc": "2.0",
        "id": 14,
        "method": "tools/call",
        "params": {"name": "mem_session_list", "arguments": {"project_key": "session-aware-demo", "limit": 1}},
    })
    assert limited_session_list["result"]["structuredContent"]["count"] == 1
    assert limited_session_list["result"]["structuredContent"]["items"][0]["external_session_id"] == "beta-thread"

    queried_session_list = server.handle_request({
        "jsonrpc": "2.0",
        "id": 15,
        "method": "tools/call",
        "params": {
            "name": "mem_session_list",
            "arguments": {"project_key": "session-aware-demo", "query": "alpha"},
        },
    })
    assert queried_session_list["result"]["structuredContent"]["count"] == 1
    assert queried_session_list["result"]["structuredContent"]["items"][0]["external_session_id"] == "alpha-thread"

    scope_resolution = server.handle_request({
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tools/call",
        "params": {
            "name": "mem_scope_resolve",
            "arguments": {"project_key": "session-aware-demo"},
        },
    })
    assert scope_resolution["result"]["structuredContent"]["routing_decision"] == "needs_hint"
    assert scope_resolution["result"]["structuredContent"]["recommended_scope"] is None
    assert scope_resolution["result"]["structuredContent"]["do_not_fetch_project_wide_pack"] is True
    assert (
        "do_not_fetch_project_wide_pack=True"
        in scope_resolution["result"]["content"][0]["text"]
    )

    bootstrap = server.handle_request({
        "jsonrpc": "2.0",
        "id": 22,
        "method": "tools/call",
        "params": {
            "name": "mem_bootstrap_context",
            "arguments": {
                "project_key": "session-aware-demo",
                "thread_hint": "alpha-thread",
                "budget": "full",
            },
        },
    })
    bootstrap_body = bootstrap["result"]["structuredContent"]
    assert bootstrap_body["selection_mode"] == "lane_needs_session_selection"
    assert bootstrap_body["session_id"] is None
    assert bootstrap_body["context_pack"] is None
    assert bootstrap_body["scope_resolution"]["recommended_scope"]["inferred_sub_scope"] == "alpha-project"
    assert "session_id" not in bootstrap_body["scope_resolution"]["recommended_scope"]
    assert "bootstrap_context" in bootstrap["result"]["content"][0]["text"]
    assert "do_not_fetch_project_wide_pack=True" in bootstrap["result"]["content"][0]["text"]

    scoped_search = server.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "mem_search",
            "arguments": {
                "query": "beta",
                "project_key": "session-aware-demo",
                "session_id": alpha_session_id,
            },
        },
    })
    assert scoped_search["result"]["structuredContent"] == {"items": [], "count": 0}

    global_search = server.handle_request({
        "jsonrpc": "2.0",
        "id": 16,
        "method": "tools/call",
        "params": {
            "name": "mem_search",
            "arguments": {"query": "alpha", "project_key": "session-aware-demo", "limit": 5},
        },
    })
    search_items = global_search["result"]["structuredContent"]["items"]
    assert search_items
    for item in search_items:
        assert item["memory_kind"] == "observation"
        assert item["retrieval_scope"] == "project"
        assert item["session_filter_applied"] is False
        assert item["project_id"]
        assert item["session_id"]
        assert item["external_session_id"]
        assert item["cwd"]
        assert item["last_captured_turn_at"]
        assert item["capture_version_status"] == "known_session_metadata"
        assert item["capture_version_scope"] == "session"

    scoped_pack = server.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {
                "project_key": "session-aware-demo",
                "budget": "full",
                "session_id": alpha_session_id,
            },
        },
    })
    body = scoped_pack["result"]["structuredContent"]
    assert body["stats"]["session_filter_applied"] is True
    assert body["stats"]["source_sessions"][0]["external_session_id"] == "alpha-thread"
    assert body["stats"]["source_sessions"][0]["last_turn_at"] == "2026-04-27T00:00:00Z"
    assert body["stats"]["source_sessions"][0]["capture_version_status"] == "known_session_metadata"
    assert body["stats"]["source_sessions"][0]["capture_version_scope"] == "session"
    assert "alpha" in body["text"]
    assert "beta" not in body["text"]

    compact_text = scoped_pack["result"]["content"][0]["text"]
    assert "session_filter=applied" in compact_text
    assert "source_sessions=1" in compact_text
    assert "not live current-turn awareness" in compact_text

    global_pack = server.handle_request({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {"project_key": "session-aware-demo", "budget": "full"},
        },
    })
    global_text = global_pack["result"]["content"][0]["text"]
    assert "session_filter=not_applied" in global_text
    assert "source_sessions=2" in global_text
    assert "scope_warning=multi_session_project_scope" in global_text
    assert "mem_session_list + session_id" in global_text
    assert "Suggested narrowing:" in global_text
    assert "persisted local context" in global_text
    assert "not live current-turn awareness" in global_text

    scoped_recent = server.handle_request({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "mem_recent",
            "arguments": {"project_key": "session-aware-demo", "session_id": alpha_session_id},
        },
    })
    assert {item["session_id"] for item in scoped_recent["result"]["structuredContent"]["items"]} == {
        alpha_session_id
    }

    scoped_open_work = server.handle_request({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "mem_open_work",
            "arguments": {"project_key": "session-aware-demo", "session_id": alpha_session_id},
        },
    })
    assert scoped_open_work["result"]["structuredContent"]["session_filter"]["external_session_id"] == "alpha-thread"

    scoped_completion = server.handle_request({
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "mem_completion_check",
            "arguments": {"project_key": "session-aware-demo", "session_id": alpha_session_id},
        },
    })
    assert scoped_completion["result"]["structuredContent"]["session_filter"]["external_session_id"] == "alpha-thread"

    scoped_scope_guard = server.handle_request({
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "mem_scope_guard",
            "arguments": {"project_key": "session-aware-demo", "session_id": alpha_session_id},
        },
    })
    assert scoped_scope_guard["result"]["structuredContent"]["session_filter"]["external_session_id"] == "alpha-thread"

    scoped_brief = server.handle_request({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "mem_project_brief",
            "arguments": {"project_key": "session-aware-demo", "session_id": alpha_session_id},
        },
    })
    assert scoped_brief["result"]["structuredContent"]["session_filter"]["external_session_id"] == "alpha-thread"

    scoped_changes = server.handle_request({
        "jsonrpc": "2.0",
        "id": 15,
        "method": "tools/call",
        "params": {
            "name": "mem_recent_changes",
            "arguments": {"project_key": "session-aware-demo", "session_id": alpha_session_id},
        },
    })
    assert scoped_changes["result"]["structuredContent"]["session_filter"]["external_session_id"] == "alpha-thread"


def test_context_pack_recommends_narrowing_for_multi_subscope_project(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    alpha_cwd = tmp_path / "alpha-project"
    beta_cwd = tmp_path / "beta-project"
    alpha_cwd.mkdir()
    beta_cwd.mkdir()
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", cwd=alpha_cwd)
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", cwd=beta_cwd)
    alpha_session_id = _session_id_by_external(store, "alpha-thread")

    global_pack = store.context_pack("session-aware-demo", budget="full")

    assert global_pack is not None
    narrowing = global_pack["stats"]["recommended_narrowing"]
    assert narrowing["reason"] == "project-wide pack spans multiple persisted sessions or inferred sub-scopes"
    assert narrowing["candidate_sub_scopes"] == ["alpha-project", "beta-project"]
    assert narrowing["confidence"] == "medium"
    assert narrowing["next_steps"][0] == {
        "tool": "mem_session_list",
        "arguments": {
            "project_key": "session-aware-demo",
            "query": "<target sub-scope>",
        },
        "then": "mem_context_pack(project_key, session_id=<chosen_session_id>)",
    }
    assert narrowing["next_steps"][1] == {
        "tool": "mem_search",
        "arguments": {
            "project_key": "session-aware-demo",
            "query": "<target sub-scope> estado actual decisiones pendientes",
        },
    }
    assert "Suggested narrowing:" in global_pack["text"]
    assert "choose a target from candidate_sub_scopes" in global_pack["text"]
    assert 'query="<target sub-scope>"' in global_pack["text"]
    assert 'query="alpha-project"' not in global_pack["text"]

    alpha_pack = store.context_pack("session-aware-demo", budget="full", session_id=alpha_session_id)

    assert alpha_pack is not None
    assert "recommended_narrowing" not in alpha_pack["stats"]
    assert "Suggested narrowing:" not in alpha_pack["text"]


def test_context_pack_narrowing_filters_system_and_policy_candidates(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    hosting_cwd = tmp_path / "hosting-runtime"
    codex_cwd = tmp_path / "codex-agent-mem"
    hosting_cwd.mkdir()
    codex_cwd.mkdir()
    _ingest_lane(store, tmp_path, "self-harm", "2026-04-27T00:00:00Z", cwd=Path("C:/Windows/System32"))
    _ingest_lane(store, tmp_path, "safety-classifier", "2026-04-27T00:01:00Z", cwd=Path("C:/Users"))
    _ingest_lane(store, tmp_path, "hosting-runtime", "2026-04-27T00:02:00Z", cwd=hosting_cwd)
    _ingest_lane(store, tmp_path, "codex-agent-mem", "2026-04-27T00:03:00Z", cwd=codex_cwd)

    global_pack = store.context_pack("session-aware-demo", budget="full")

    assert global_pack is not None
    narrowing = global_pack["stats"]["recommended_narrowing"]
    assert narrowing["candidate_sub_scopes"] == ["codex-agent-mem", "hosting-runtime"]
    assert "System32" not in narrowing["candidate_sub_scopes"]
    assert "self-harm" not in narrowing["candidate_sub_scopes"]
    assert "safety-classifier" not in narrowing["candidate_sub_scopes"]
    assert narrowing["next_steps"][0]["arguments"]["query"] == "<target sub-scope>"
    assert 'query="<target sub-scope>"' in global_pack["text"]
    assert 'query="codex-agent-mem"' not in global_pack["text"]
    assert 'query="System32"' not in global_pack["text"]


def test_context_pack_narrowing_uses_placeholder_when_candidates_are_noise(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _ingest_lane(store, tmp_path, "self-harm", "2026-04-27T00:00:00Z", cwd=Path("C:/Windows/System32"))
    _ingest_lane(store, tmp_path, "safety-classifier", "2026-04-27T00:01:00Z", cwd=Path("C:/Users"))

    global_pack = store.context_pack("session-aware-demo", budget="full")

    assert global_pack is not None
    narrowing = global_pack["stats"]["recommended_narrowing"]
    assert narrowing["candidate_sub_scopes"] == []
    assert narrowing["confidence"] == "low"
    assert narrowing["next_steps"][0]["arguments"]["query"] == "<target sub-scope>"
    assert narrowing["next_steps"][1]["arguments"]["query"] == "<target sub-scope> estado actual decisiones pendientes"
    assert 'query="<target sub-scope>"' in global_pack["text"]


def test_session_id_must_belong_to_project(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", project_key="project-alpha")
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", project_key="project-beta")
    beta_session_id = _session_id_by_external(store, "beta-thread", project_key="project-beta")
    server = CodexAgentMemMCPServer(
        store,
        MCPRuntimeState(db_path=tmp_path / "codex_agent_mem.db", idle_timeout_seconds=300),
    )

    response = server.handle_request({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {
                "project_key": "project-alpha",
                "budget": "full",
                "session_id": beta_session_id,
            },
        },
    })

    assert response["result"]["isError"] is True
    assert "Session not found for project" in response["result"]["structuredContent"]["error"]


def test_snapshot_provenance_requires_explicit_session_for_broad_scope(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z")
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z")
    alpha_session_id = _session_id_by_external(store, "alpha-thread")

    unscoped = store.snapshot_create("session-aware-demo", "unscoped-project-snapshot")
    assert unscoped is not None
    assert unscoped["session_id"] is None
    assert unscoped["external_session_id"] is None
    assert unscoped["provenance_confidence"] == "low"
    assert "not associated" in unscoped["provenance_warning"]

    scoped = store.snapshot_create(
        "session-aware-demo",
        "alpha-session-snapshot",
        session_id=alpha_session_id,
    )
    assert scoped is not None
    assert scoped["session_id"] == alpha_session_id
    assert scoped["external_session_id"] == "alpha-thread"
    assert scoped["provenance_confidence"] == "high"
    assert scoped["provenance_warning"] is None
    assert scoped["cwd"] == str(tmp_path)
    assert scoped["project_root_path"] == str(tmp_path)
    assert "alpha" in scoped["display_label"]

    payload = json.loads(Path(scoped["snapshot_path"]).read_text(encoding="utf-8"))
    assert payload["context_pack"]["stats"]["session_filter_applied"] is True
    assert payload["context_pack"]["stats"]["source_sessions"][0]["external_session_id"] == "alpha-thread"

    snapshots = store.list_snapshots("session-aware-demo")
    by_id = {item["snapshot_id"]: item for item in snapshots}
    assert by_id[scoped["snapshot_id"]]["session_id"] == alpha_session_id
    assert by_id[scoped["snapshot_id"]]["external_session_id"] == "alpha-thread"
    assert by_id[scoped["snapshot_id"]]["provenance_confidence"] == "high"
    assert by_id[unscoped["snapshot_id"]]["session_id"] is None
    assert by_id[unscoped["snapshot_id"]]["provenance_confidence"] == "low"


def test_snapshot_session_id_must_belong_to_project(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z", project_key="project-alpha")
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z", project_key="project-beta")
    beta_session_id = _session_id_by_external(store, "beta-thread", project_key="project-beta")

    with pytest.raises(ValueError, match="Session not found for project"):
        store.snapshot_create("project-alpha", "wrong-session", session_id=beta_session_id)


def test_known_pack_hash_is_session_scope_aware(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z")
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z")
    alpha_session_id = _session_id_by_external(store, "alpha-thread")
    server = CodexAgentMemMCPServer(
        store,
        MCPRuntimeState(db_path=tmp_path / "codex_agent_mem.db", idle_timeout_seconds=300),
    )

    global_pack = server.handle_request({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {"project_key": "session-aware-demo", "budget": "full"},
        },
    })
    global_hash = global_pack["result"]["structuredContent"]["pack_hash"]

    scoped_pack = server.handle_request({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {
                "project_key": "session-aware-demo",
                "budget": "full",
                "session_id": alpha_session_id,
                "known_pack_hash": global_hash,
            },
        },
    })

    body = scoped_pack["result"]["structuredContent"]
    assert body.get("not_modified") is not True
    assert body["pack_hash"] != global_hash
    assert body["stats"]["session_filter_applied"] is True


def test_known_pack_hash_ignores_volatile_memory_age(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z")
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z")
    alpha_session_id = _session_id_by_external(store, "alpha-thread")
    server = CodexAgentMemMCPServer(
        store,
        MCPRuntimeState(db_path=tmp_path / "codex_agent_mem.db", idle_timeout_seconds=300),
    )

    global_pack = server.handle_request({
        "jsonrpc": "2.0",
        "id": 17,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {"project_key": "session-aware-demo", "budget": "full"},
        },
    })
    global_hash = global_pack["result"]["structuredContent"]["pack_hash"]

    scoped_pack = server.handle_request({
        "jsonrpc": "2.0",
        "id": 18,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {
                "project_key": "session-aware-demo",
                "budget": "full",
                "session_id": alpha_session_id,
            },
        },
    })
    scoped_hash = scoped_pack["result"]["structuredContent"]["pack_hash"]

    time.sleep(1.2)

    global_repeat = server.handle_request({
        "jsonrpc": "2.0",
        "id": 19,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {
                "project_key": "session-aware-demo",
                "budget": "full",
                "known_pack_hash": global_hash,
            },
        },
    })
    assert global_repeat["result"]["structuredContent"]["not_modified"] is True
    assert global_repeat["result"]["structuredContent"]["pack_hash"] == global_hash

    scoped_repeat = server.handle_request({
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tools/call",
        "params": {
            "name": "mem_context_pack",
            "arguments": {
                "project_key": "session-aware-demo",
                "budget": "full",
                "session_id": alpha_session_id,
                "known_pack_hash": scoped_hash,
            },
        },
    })
    assert scoped_repeat["result"]["structuredContent"]["not_modified"] is True
    assert scoped_repeat["result"]["structuredContent"]["pack_hash"] == scoped_hash


def test_session_list_includes_sessions_without_observations_and_clamps_limit(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_id = store.upsert_project("empty-session-demo", str(tmp_path))
    with store.conn:
        for index in range(105):
            store.conn.execute(
                """
                INSERT INTO sessions(project_id, runtime, external_session_id, started_at, cwd, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    "codex",
                    f"empty-{index:03d}",
                    f"2026-04-27T00:{index % 60:02d}:00Z",
                    str(tmp_path),
                    "{}",
                ),
            )

    sessions = store.list_sessions("empty-session-demo", limit=999)
    assert len(sessions) == 100
    assert sessions[0]["observation_count"] == 0
    assert sessions[0]["turn_count"] == 0
    assert sessions[0]["first_input_preview"] == ""
    assert sessions[0]["display_label"].startswith("empty-")
    assert sessions[0]["capture_version_status"] == "unknown"
    assert sessions[0]["capture_version_scope"] == "none"


def test_internal_title_prompt_does_not_become_operational_label(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_id = store.upsert_project("label-demo", str(tmp_path))
    with store.conn:
        cur = store.conn.execute(
            """
            INSERT INTO sessions(project_id, runtime, external_session_id, started_at, cwd, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "codex",
                "title-noise-thread",
                "2026-04-27T00:00:00Z",
                str(tmp_path),
                "{}",
            ),
        )
        session_id = int(cur.lastrowid)
        store.conn.execute(
            """
            INSERT INTO turns(
              session_id, external_turn_id, captured_at, input_messages_json,
              assistant_message, tool_events_json, raw_payload_json, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "title-turn",
                "2026-04-27T00:00:00Z",
                store._json([
                    "You are a helpful assistant. Generate a concise UI title for a coding-related task."
                ]),
                "",
                "[]",
                "{}",
                "title-noise",
            ),
        )

    sessions = store.list_sessions("label-demo")
    assert sessions[0]["low_value_session"] is True
    assert sessions[0]["low_value_reason"] == "internal_title_generation_prompt"
    assert sessions[0]["internal_prompt_suppressed"] is True
    assert "Generate a concise UI title" not in sessions[0]["display_label"]
    assert sessions[0]["project_id"] == project_id
    assert sessions[0]["session_id"] == session_id
    assert sessions[0]["capture_version_status"] == "unknown"
    assert sessions[0]["capture_version_scope"] == "none"


def test_session_label_uses_later_operational_turn_when_first_turn_is_noise(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_id = store.upsert_project("label-demo-later-turn", str(tmp_path))
    with store.conn:
        cur = store.conn.execute(
            """
            INSERT INTO sessions(project_id, runtime, external_session_id, started_at, cwd, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "codex",
                "later-real-thread",
                "2026-04-27T00:00:00Z",
                str(tmp_path),
                "{}",
            ),
        )
        session_id = int(cur.lastrowid)
        store.conn.execute(
            """
            INSERT INTO turns(
              session_id, external_turn_id, captured_at, input_messages_json,
              assistant_message, tool_events_json, raw_payload_json, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "title-turn",
                "2026-04-27T00:00:00Z",
                store._json([
                    "You are a helpful assistant. Generate a concise UI title for a coding-related task."
                ]),
                "",
                "[]",
                "{}",
                "title-noise",
            ),
        )
        store.conn.execute(
            """
            INSERT INTO turns(
              session_id, external_turn_id, captured_at, input_messages_json,
              assistant_message, tool_events_json, raw_payload_json, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "real-turn",
                "2026-04-27T00:01:00Z",
                store._json([
                    "Fix codex-agent-mem v1.0.1 memory scope stress labels and retrieval hygiene."
                ]),
                "",
                "[]",
                "{}",
                "real-turn",
            ),
        )

    sessions = store.list_sessions("label-demo-later-turn")
    assert sessions[0]["low_value_session"] is False
    assert sessions[0]["internal_prompt_suppressed"] is True
    assert "codex-agent-mem" in sessions[0]["display_label"]
    assert "Generate a concise UI title" not in sessions[0]["display_label"]
    assert sessions[0]["first_operational_input_preview"].startswith("Fix codex-agent-mem")


def test_dedup_and_dominance_guard_reduce_global_pack_noise(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    duplicate_summary = "C:\\WORKSPACES\\demo\\codex-agent-mem is the local Git staging source for v1.0.1."
    for index in range(12):
        _insert_observation(
            store,
            tmp_path,
            project_key="noise-demo",
            external_session_id="dupe-thread",
            external_turn_id=f"dupe-turn-{index}",
            timestamp=f"2026-04-27T00:{index:02d}:00Z",
            summary=duplicate_summary,
        )
    for index in range(12):
        _insert_observation(
            store,
            tmp_path,
            project_key="noise-demo",
            external_session_id="large-thread",
            external_turn_id=f"large-turn-{index}",
            timestamp=f"2026-04-27T01:{index:02d}:00Z",
            summary=f"Large lane unique operational item {index} for codex-agent-mem release hardening.",
        )
    _insert_observation(
        store,
        tmp_path,
        project_key="noise-demo",
        external_session_id="small-thread",
        external_turn_id="small-turn",
        timestamp="2026-04-27T02:00:00Z",
        summary="hosting-runtime belongs to a different operational lane.",
    )

    search = store.search_observations("local Git staging", project_key="noise-demo", limit=20)
    assert len(search) == 1
    assert search[0]["dedupe_applied"] is True
    assert search[0]["duplicate_count"] == 12

    pack = store.context_pack("noise-demo", budget="full")
    assert pack is not None
    assert pack["stats"]["dedupe"]["duplicates_collapsed"] >= 1
    assert pack["stats"]["dominance_guard"]["dominance_guard_applied"] is True
    assert pack["stats"]["dominance_guard"]["sessions_capped"]


def test_dedup_preserves_same_text_with_different_type_or_status(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    shared_summary = "Update release notes for the v1.0.1 scope hardening fix."
    _insert_observation(
        store,
        tmp_path,
        project_key="dedupe-status-demo",
        external_session_id="pending-thread",
        external_turn_id="pending-turn",
        timestamp="2026-04-27T00:00:00Z",
        summary=shared_summary,
        obs_type="pending_item",
        status="active",
    )
    _insert_observation(
        store,
        tmp_path,
        project_key="dedupe-status-demo",
        external_session_id="completed-thread",
        external_turn_id="completed-turn",
        timestamp="2026-04-27T00:01:00Z",
        summary=shared_summary,
        obs_type="completed_item",
        status="done",
    )
    _insert_observation(
        store,
        tmp_path,
        project_key="dedupe-status-demo",
        external_session_id="completed-thread",
        external_turn_id="completed-turn-2",
        timestamp="2026-04-27T00:02:00Z",
        summary=shared_summary,
        obs_type="completed_item",
        status="done",
    )

    search = store.search_observations("release notes", project_key="dedupe-status-demo", limit=20)
    typed = {(item["type"], item["status"]): item for item in search if item["summary"] == shared_summary}
    assert ("pending_item", "active") in typed
    assert ("completed_item", "done") in typed
    assert typed[("pending_item", "active")]["duplicate_count"] == 1
    assert typed[("completed_item", "done")]["duplicate_count"] == 2


def test_small_global_pack_preserves_budget_with_scope_warning(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _ingest_lane(store, tmp_path, "alpha", "2026-04-27T00:00:00Z")
    _ingest_lane(store, tmp_path, "beta", "2026-04-27T00:01:00Z")

    pack = store.context_pack("session-aware-demo", max_chars=400)
    assert pack is not None
    assert pack["stats"]["scope_warning"]["code"] == "multi_session_project_scope"
    assert "Scope warning:" in pack["text"]
    assert len(pack["text"]) <= 400


def test_search_overfetches_before_dedupe(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    for index in range(5):
        _insert_observation(
            store,
            tmp_path,
            project_key="overfetch-demo",
            external_session_id=f"unique-thread-{index}",
            external_turn_id=f"unique-turn-{index}",
            timestamp=f"2026-04-27T00:{index:02d}:00Z",
            summary=f"shared search term unique result {index}",
        )
    for index in range(20):
        _insert_observation(
            store,
            tmp_path,
            project_key="overfetch-demo",
            external_session_id="duplicate-thread",
            external_turn_id=f"duplicate-turn-{index}",
            timestamp=f"2026-04-27T01:{index:02d}:00Z",
            summary="shared search term duplicated result",
        )

    results = store.search_observations("shared search term", project_key="overfetch-demo", limit=5)
    summaries = {item["summary"] for item in results}
    assert "shared search term duplicated result" in summaries
    assert any(summary.startswith("shared search term unique result") for summary in summaries)
    assert len(results) == 5


def test_dominance_guard_uses_expanded_pool_and_preserves_smaller_session(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    for index in range(300):
        _insert_observation(
            store,
            tmp_path,
            project_key="dominance-pool-demo",
            external_session_id="huge-thread",
            external_turn_id=f"huge-turn-{index}",
            timestamp=f"2026-04-27T03:{index % 60:02d}:00Z",
            summary=f"huge session generic item {index}",
        )
    _insert_observation(
        store,
        tmp_path,
        project_key="dominance-pool-demo",
        external_session_id="small-thread",
        external_turn_id="small-turn",
        timestamp="2026-04-27T00:00:00Z",
        summary="small session still relevant after expanded pool selection",
    )

    pack = store.context_pack("dominance-pool-demo", budget="full")
    assert pack is not None
    source_ids = {item["external_session_id"] for item in pack["stats"]["source_sessions"]}
    assert "small-thread" in source_ids
    assert pack["stats"]["dominance_guard"]["dominance_guard_applied"] is True


def test_dominance_guard_preserves_protected_operational_items(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    for index in range(20):
        _insert_observation(
            store,
            tmp_path,
            project_key="protected-cap-demo",
            external_session_id="busy-thread",
            external_turn_id=f"generic-turn-{index}",
            timestamp=f"2026-04-27T00:{index:02d}:00Z",
            summary=f"generic busy session item {index}",
            obs_type="user_request",
        )
    _insert_observation(
        store,
        tmp_path,
        project_key="protected-cap-demo",
        external_session_id="busy-thread",
        external_turn_id="blocker-turn",
        timestamp="2026-04-27T00:59:00Z",
        summary="critical blocker must survive per-session dominance cap",
        obs_type="blocker",
    )
    _insert_observation(
        store,
        tmp_path,
        project_key="protected-cap-demo",
        external_session_id="other-thread",
        external_turn_id="other-turn",
        timestamp="2026-04-27T01:00:00Z",
        summary="other session triggers project-wide dominance guard",
    )

    pack = store.context_pack("protected-cap-demo", budget="full")
    assert pack is not None
    assert "critical blocker must survive per-session dominance cap" in pack["text"]
    assert pack["stats"]["dominance_guard"]["protected_items_retained"] >= 1


def test_operational_freshness_ignores_recent_internal_prompt(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _insert_observation(
        store,
        tmp_path,
        project_key="freshness-demo",
        external_session_id="freshness-thread",
        external_turn_id="operational-turn",
        timestamp="2026-04-27T00:00:00Z",
        summary="operational memory should define freshness",
    )
    session_id = _session_id_by_external(store, "freshness-thread", project_key="freshness-demo")
    with store.conn:
        store.conn.execute(
            """
            INSERT INTO turns(
              session_id, external_turn_id, captured_at, input_messages_json,
              assistant_message, tool_events_json, raw_payload_json, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "title-turn",
                "2026-04-27T01:00:00Z",
                store._json([
                    "You are a helpful assistant. Generate a concise UI title for a coding-related task."
                ]),
                "",
                "[]",
                "{}",
                "title-turn",
            ),
        )

    pack = store.context_pack("freshness-demo", budget="full")
    assert pack is not None
    assert pack["stats"]["last_captured_turn_at"] == "2026-04-27T01:00:00Z"
    assert pack["stats"]["last_operational_capture_at"] == "2026-04-27T00:00:00Z"
    assert "last_operational_capture_at=" in compact_text_summary(pack)


def test_dedup_representative_tracks_latest_duplicate_provenance(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    summary = "duplicate provenance should keep the newest captured turn"
    _insert_observation(
        store,
        tmp_path,
        project_key="duplicate-provenance-demo",
        external_session_id="old-thread",
        external_turn_id="old-turn",
        timestamp="2026-04-27T00:00:00Z",
        summary=summary,
    )
    _insert_observation(
        store,
        tmp_path,
        project_key="duplicate-provenance-demo",
        external_session_id="new-thread",
        external_turn_id="new-turn",
        timestamp="2026-04-27T02:00:00Z",
        summary=summary,
    )

    results = store.search_observations("duplicate provenance", project_key="duplicate-provenance-demo", limit=5)
    assert len(results) == 1
    assert results[0]["duplicate_count"] == 2
    assert results[0]["duplicate_latest_captured_turn_at"] == "2026-04-27T02:00:00Z"
    assert sorted(results[0]["duplicate_external_session_ids"]) == ["new-thread", "old-thread"]


def test_upsert_session_merges_metadata_without_clobbering_existing_keys(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    project_id = store.upsert_project("metadata-merge-demo", str(tmp_path))
    first_payload = {
        "runtime": "codex",
        "project_key": "metadata-merge-demo",
        "session_id": "metadata-thread",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "timestamp": "2026-04-27T00:00:00Z",
        "input_messages": ["metadata merge first event"],
        "assistant_message": "",
        "metadata": {"source": "codex", "model": "gpt-test"},
    }
    second_payload = {
        **first_payload,
        "turn_id": "turn-2",
        "timestamp": "2026-04-27T00:01:00Z",
        "metadata": {"source": "codex-second", "model": None, "empty_note": ""},
    }

    store.upsert_session(project_id, normalize_event(first_payload))
    store.upsert_session(project_id, normalize_event(second_payload))
    row = store.conn.execute(
        "SELECT metadata_json FROM sessions WHERE project_id = ? AND external_session_id = ?",
        (project_id, "metadata-thread"),
    ).fetchone()
    metadata = store._load_json(row["metadata_json"], {})
    assert metadata["model"] == "gpt-test"
    assert metadata["source"] == "codex-second"
    assert "empty_note" not in metadata
    assert metadata["producer_version_first_seen"] == "1.0.1"
    assert metadata["producer_version_last_seen"] == "1.0.1"


def test_session_list_can_filter_by_query_and_sub_scope_hint(tmp_path: Path):
    store = CodexAgentMemStore(tmp_path / "codex_agent_mem.db")
    _insert_observation(
        store,
        tmp_path,
        project_key="session-query-demo",
        external_session_id="codex-thread",
        external_turn_id="codex-turn",
        timestamp="2026-04-27T00:00:00Z",
        summary="Plan codex-agent-mem retrieval hardening in C:\\WORKSPACES\\multi-project\\codex-agent-mem.",
    )
    _insert_observation(
        store,
        tmp_path,
        project_key="session-query-demo",
        external_session_id="hosting-thread",
        external_turn_id="hosting-turn",
        timestamp="2026-04-27T00:01:00Z",
        summary="Plan hosting-runtime deploy work in C:\\WORKSPACES\\multi-project\\hosting-runtime.",
    )

    query_results = store.list_sessions("session-query-demo", query="codex-agent-mem")
    assert {item["external_session_id"] for item in query_results} == {"codex-thread"}

    hint_results = store.list_sessions("session-query-demo", sub_scope_hint="hosting-runtime")
    assert {item["external_session_id"] for item in hint_results} == {"hosting-thread"}
