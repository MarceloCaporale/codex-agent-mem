# Quickstart

This is the shortest path from clone to a working local setup.

## 1. Clone and install

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## 2. Verify the package

```powershell
codex-agent-mem-smoke
```

That should insert a sample turn into a local SQLite database and verify retrieval.

## 3. Generate Codex config

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Paste the generated output into `~/.codex/config.toml`.
The snippet already includes read-only MCP tool approvals needed for non-interactive Codex runs.

## 4. Optional local services

Start the inspection API:

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Then open the local inspector:

```text
http://127.0.0.1:37770/ui
```

Start the MCP server:

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

## 5. Run full checks

```powershell
ruff check .
python -m compileall src
pytest -q
python -m build
```
