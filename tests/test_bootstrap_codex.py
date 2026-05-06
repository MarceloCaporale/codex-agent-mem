from pathlib import Path

import pytest

from codex_agent_mem.bootstrap_codex import _tools_for_profile, build_codex_toml_snippet
from codex_agent_mem.mcp_stdio import (
    MUTATING_TOOLS,
    CodexAgentMemMCPServer,
    MCPRuntimeState,
    StoreProvider,
)


class DummyStoreProvider(StoreProvider):
    def get(self):  # pragma: no cover - list_tools must not open the store.
        raise AssertionError("bootstrap profile tests must not open SQLite")

    def close(self) -> None:
        return None


def _listed_tool_names(profile: str) -> tuple[str, ...]:
    server = CodexAgentMemMCPServer(
        DummyStoreProvider(),
        MCPRuntimeState(
            db_path=Path("unused.db"),
            idle_timeout_seconds=None,
            profile=profile,
        ),
    )
    return tuple(str(tool["name"]) for tool in server.list_tools())


@pytest.mark.parametrize("profile", ["minimal", "standard", "full"])
def test_bootstrap_tool_approvals_match_mcp_profile_surface(profile):
    listed_tools = _listed_tool_names(profile)
    assert _tools_for_profile(profile, read_only=False) == listed_tools
    assert _tools_for_profile(profile, read_only=True) == tuple(
        tool for tool in listed_tools if tool not in MUTATING_TOOLS
    )


def test_bootstrap_codex_snippet_uses_literal_paths():
    snippet = build_codex_toml_snippet(
        python_exe=r"C:\Tools\Python\python.exe",
        db_path=Path(r"C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db"),
    )
    assert '[mcp_servers."codex-agent-mem"]' in snippet
    assert "'C:\\Tools\\Python\\python.exe'" in snippet
    assert "'C:\\Users\\YOU\\.codex_agent_mem\\codex_agent_mem.db'" in snippet
    assert "--project-from-cwd" in snippet
    assert "--sync-project-doc" not in snippet
    assert "--idle-timeout-seconds" in snippet
    assert "'300'" in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_search]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_get]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_recent]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_session_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_scope_resolve]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_bootstrap_context]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_project_brief]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_open_work]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_completion_check]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_recent_changes]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_scope_guard]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_context_pack]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_provenance]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_health]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_health_runtime]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_snapshot_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_note_create]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_snapshot_create]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_snapshot_restore]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_policy_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_policy_validate]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_policy_add]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_policy_remove]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_inheritance_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_inheritance_add]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_inheritance_remove]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_repair_propose]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_repair_apply]' in snippet
    assert snippet.count('approval_mode = "approve"') == 28


def test_bootstrap_codex_snippet_can_opt_into_project_doc_sync():
    snippet = build_codex_toml_snippet(
        python_exe=r"C:\Tools\Python\python.exe",
        db_path=Path(r"C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db"),
        sync_project_doc=True,
        idle_timeout_seconds=180,
    )
    assert "--sync-project-doc" in snippet
    assert "'180'" in snippet


def test_bootstrap_codex_snippet_can_emit_minimal_read_only_profile():
    snippet = build_codex_toml_snippet(
        python_exe=r"C:\Tools\Python\python.exe",
        db_path=Path(r"C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db"),
        mcp_profile="minimal",
        mcp_read_only=True,
        response_mode="compact",
    )
    assert "--profile" in snippet
    assert "'minimal'" in snippet
    assert "--read-only" in snippet
    assert "--response-mode" in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_session_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_scope_resolve]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_bootstrap_context]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_open_work]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_completion_check]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_context_pack]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_health_runtime]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_search]' not in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_note_create]' not in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_snapshot_create]' not in snippet
    assert snippet.count('approval_mode = "approve"') == 7


def test_bootstrap_codex_standard_profile_is_read_oriented():
    snippet = build_codex_toml_snippet(
        python_exe=r"C:\Tools\Python\python.exe",
        db_path=Path(r"C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db"),
        mcp_profile="standard",
    )
    assert '[mcp_servers."codex-agent-mem".tools.mem_search]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_session_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_scope_resolve]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_bootstrap_context]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_snapshot_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_note_create]' not in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_snapshot_create]' not in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_policy_add]' not in snippet
    assert snippet.count('approval_mode = "approve"') == 20


def test_codex_example_config_is_writable_by_default():
    example = Path("examples/codex/config.toml.example").read_text(encoding="utf-8")
    assert "'full'" in example
    assert "--read-only" not in example
    assert '[mcp_servers."codex-agent-mem".tools.mem_note_create]' in example
    assert '[mcp_servers."codex-agent-mem".tools.mem_scope_resolve]' in example
    assert '[mcp_servers."codex-agent-mem".tools.mem_bootstrap_context]' in example

    audit_example = Path("examples/codex/config.read-only-audit.example.toml").read_text(
        encoding="utf-8"
    )
    assert "retrieval-only audit/debug" in audit_example
    assert "'minimal'" in audit_example
    assert "--read-only" in audit_example
    assert '[mcp_servers."codex-agent-mem".tools.mem_scope_resolve]' in audit_example
    assert '[mcp_servers."codex-agent-mem".tools.mem_bootstrap_context]' in audit_example
