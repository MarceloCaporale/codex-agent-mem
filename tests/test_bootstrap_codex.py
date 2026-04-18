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
    assert "--sync-project-doc" in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_search]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_get]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_recent]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_project_brief]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_open_work]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_completion_check]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_recent_changes]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_scope_guard]' in snippet
    assert '[mcp_servers."codex-agent-mem".tools.mem_context_pack]' in snippet
    assert snippet.count('approval_mode = "approve"') == 9
