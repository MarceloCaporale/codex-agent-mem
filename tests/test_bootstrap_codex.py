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
