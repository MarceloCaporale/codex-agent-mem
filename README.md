# codex-agent-mem

Other languages: [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Portable, local-first memory for Codex and coding-agent workflows.

codex-agent-mem persists durable findings from agent turns into local SQLite, exposes compact retrieval over MCP, and keeps the memory layer auditable and runtime-owned instead of hiding it inside one vendor runtime.

## Status

`0.2.0` is the current public baseline release.

What works today:

- Codex `notify` ingestion on `agent-turn-complete`
- local SQLite persistence with FTS5
- heuristic extraction of `session_summary` and `decision`
- FastAPI inspection API
- MCP stdio server with:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
- automated tests

What is intentionally not in scope yet:

- embeddings
- vector stores
- UI
- Codex App Server ingestion
- Codex hooks adapter
- Ollama adapter
- multi-agent orchestration

## Important expectation

Codex does not currently install arbitrary MCP tools from a GitHub URL in one step.

The supported path is still:

1. install the Python package
2. point Codex `notify` and `mcp_servers` at the installed commands

This repository is prepared so that workflow is clean and repeatable.

## Install

### Option A: `pipx` from GitHub

Install directly from the repository URL:

```powershell
pipx install "git+https://github.com/<org>/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### Option B: local development install

```powershell
git clone <repo-url>
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

## Configure Codex

Generate a ready-to-paste snippet:

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

That prints the `notify` and `[mcp_servers."codex-agent-mem"]` blocks you can paste into `~/.codex/config.toml`.

Example files also live under [examples/codex](./examples/codex/).

## Run locally

Start the inspection API:

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Start the MCP server:

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

## Quick verification

Run the smoke test:

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

That inserts a sample turn, extracts observations, and verifies recent retrieval and project brief generation.

## Repository layout

- [src/codex_agent_mem](./src/codex_agent_mem/) - package code
- [tests](./tests/) - executable tests
- [examples/codex](./examples/codex/) - Codex integration examples
- [scripts](./scripts/) - local bootstrap helpers
- [docs](./docs/) - architecture and release notes

## Release surface

This repository includes:

- clean root package layout
- installable `pyproject.toml`
- command entry points
- tests
- CI workflow
- license
- changelog
