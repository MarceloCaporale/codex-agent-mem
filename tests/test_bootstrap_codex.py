from pathlib import Path

from codex_agent_mem.bootstrap_codex import build_codex_toml_snippet


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
    assert '[mcp_servers."codex-agent-mem".tools.mem_snapshot_create]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_snapshot_restore]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_policy_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_policy_validate]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_inheritance_list]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_repair_propose]' in snippet
    assert snippet.count('approval_mode = "approve"') == 19


def test_bootstrap_codex_snippet_can_opt_into_project_doc_sync():
    snippet = build_codex_toml_snippet(
        python_exe=r"C:\Tools\Python\python.exe",
        db_path=Path(r"C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db"),
        sync_project_doc=True,
        idle_timeout_seconds=180,
    )
    assert "--sync-project-doc" in snippet
    assert "'180'" in snippet
