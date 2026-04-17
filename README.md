# codex-agent-mem

Other languages: [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Portable, auditable, local-first memory for Codex with SQLite persistence, notify capture, and MCP retrieval.

codex-agent-mem persists durable findings from agent turns into local SQLite, exposes compact retrieval over MCP, and keeps the memory layer auditable and runtime-owned instead of hiding it inside one vendor runtime.

Key docs: [AGENTS.md](./AGENTS.md) | [Quickstart](./docs/quickstart.md) | [Codex Integration](./docs/codex-integration.md) | [Support Matrix](./docs/support-matrix.md) | [Design Decisions](./docs/design-decisions.md) | [Discoverability Metadata](./docs/discoverability.md)

## Status

`0.2.1` is the current public baseline release.

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

## Why this repository exists

- Codex workflows often need durable context that stays outside the runtime.
- MCP is useful for retrieval, but durable project memory still needs explicit storage and capture.
- SQLite keeps the implementation local-first, auditable, and easy to inspect.
- The current release intentionally focuses on a narrow, testable slice rather than a broad unfinished platform.

## Important expectation

Codex does not currently install arbitrary MCP tools from a GitHub URL in one step.

The supported path is still:

1. install the Python package
2. point Codex `notify` and `mcp_servers` at the installed commands

This repository is prepared so that workflow is clean and repeatable.

## Quickstart

If you want the shortest path from clone to a working local setup:

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Then paste the generated snippet into `~/.codex/config.toml`.

## Install

### Option A: `pipx` from GitHub

Install directly from the repository URL:

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### Option B: local development install

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
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

That prints the `notify` block, the `[mcp_servers."codex-agent-mem"]` block, and read-only MCP tool approvals you can paste into `~/.codex/config.toml`.

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
- [docs](./docs/) - architecture, integration, quickstart, and release notes

## Documentation map

- [AGENTS.md](./AGENTS.md) - repo map and operational guide for coding agents
- [docs/quickstart.md](./docs/quickstart.md) - shortest install and first-run path
- [docs/codex-integration.md](./docs/codex-integration.md) - how notify and MCP fit into Codex
- [docs/support-matrix.md](./docs/support-matrix.md) - current support and known gaps
- [docs/design-decisions.md](./docs/design-decisions.md) - explicit product and architecture decisions
- [docs/architecture.md](./docs/architecture.md) - narrow technical architecture of the current release
- [CONTRIBUTING.md](./CONTRIBUTING.md) - contribution workflow and quality bar
- [SECURITY.md](./SECURITY.md) - support scope and security reporting guidance
- [docs/discoverability.md](./docs/discoverability.md) - recommended GitHub description, topics, and release framing

## Release surface

This repository includes:

- clean root package layout
- installable `pyproject.toml`
- command entry points
- tests
- CI workflow
- license
- changelog
