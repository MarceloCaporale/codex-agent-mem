# Quickstart

This is the shortest path from clone to a working local setup.

## 1. Clone and install

### PowerShell / Windows

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

### bash / macOS / Linux

```bash
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 2. Verify the package

```bash
codex-agent-mem-smoke
```

```powershell
codex-agent-mem-smoke
```

That should insert a sample turn into a local SQLite database and verify retrieval.

## 3. Generate Codex config

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Paste the generated output into `~/.codex/config.toml`.
The snippet already includes `--sync-project-doc` plus read-only MCP tool approvals needed for non-interactive Codex runs.

## 4. Optional local services

Start the inspection API:

```bash
codex-agent-mem-api --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Then open the local inspector:

```text
http://127.0.0.1:37770/ui
```

Start the MCP server:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

## 5. Rebuild the generated continuity block manually

```bash
codex-agent-mem-refresh-context --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db" --project-key YOUR_PROJECT --cwd /path/to/project
```

```powershell
codex-agent-mem-refresh-context --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --project-key YOUR_PROJECT --cwd C:\Path\To\Project
```

## 6. Run full checks

```powershell
ruff check .
python -m compileall src
pytest -q
python -m build
```
