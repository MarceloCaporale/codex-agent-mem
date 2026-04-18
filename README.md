# codex-agent-mem

Other languages: [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Portable, auditable, local-first memory for Codex with SQLite persistence, compact context reinjection, and MCP retrieval.

codex-agent-mem persists durable findings from agent turns into local SQLite, compiles a smaller working-memory pack from recent context, syncs that pack into `AGENTS.md` when it is actually smaller than the source context, and exposes compact retrieval over MCP.

Key docs: [AGENTS.md](./AGENTS.md) | [Quickstart](./docs/quickstart.md) | [Codex Integration](./docs/codex-integration.md) | [Support Matrix](./docs/support-matrix.md) | [Design Decisions](./docs/design-decisions.md) | [Discoverability Metadata](./docs/discoverability.md)

## Status

`0.5.0` is the current public baseline release.

What works today:

- Codex `notify` ingestion on `agent-turn-complete`
- local SQLite persistence with FTS5
- heuristic extraction of `session_summary`, `decision`, `objective`, `constraint`, `pending_item`, `completed_item`, `blocker`, and `completion_claim`
- generated working-memory packs with approximate token budget and compression stats
- automatic `AGENTS.md` sync when the generated pack is smaller than the source context
- operational-state carry-forward so the next run can recover objective, pending work, blockers, and scope guardrails
- false-completion guardrails that keep “done” from overriding open work when pending items or blockers still exist
- context sync metrics persisted per project
- FastAPI inspection API
- local inspection UI at `/ui`
- MCP stdio server with:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
  - `mem_context_pack`
- automated tests

What is intentionally not in scope yet:

- embeddings
- vector stores
- Codex App Server ingestion
- Codex hooks adapter
- Ollama adapter
- multi-agent orchestration

## Why this repository exists

- Codex workflows often need durable context that stays outside the runtime.
- Retrieval alone does not solve the bigger failure mode: losing scope and forcing the user to restate prior context.
- A compressed continuity block that Codex loads automatically can reduce how much prior context must be replayed manually.
- Carrying only decisions is not enough; the runtime also needs active objective, open work, blockers, and a rule against false closure.
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

That prints the `notify` block, the `[mcp_servers."codex-agent-mem"]` block, the `--sync-project-doc` flag for automatic context reinjection, and read-only MCP tool approvals you can paste into `~/.codex/config.toml`.

Example files also live under [examples/codex](./examples/codex/).

## Run locally

Start the inspection API:

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Then open:

```text
http://127.0.0.1:37770/ui
```

Start the MCP server:

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Manually rebuild the generated continuity block for one directory:

```powershell
codex-agent-mem-refresh-context --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --project-key YOUR_PROJECT --cwd C:\Path\To\Project
```

## Quick verification

Run the smoke test:

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

That inserts a sample turn, extracts observations, and verifies recent retrieval and project brief generation.

## What saves tokens now

- The package compiles a smaller working-memory pack from recent turns, durable decisions, and derived operational state.
- When that pack is actually smaller than the source context, it is synced into `AGENTS.md` for the working directory.
- Codex loads `AGENTS.md` before the user prompt, so future sessions can start with compressed continuity instead of forcing you to restate old scope.
- `mem_context_pack` exposes the same compact pack over MCP for on-demand retrieval.
- The pack now carries forward pending work and blockers, so a future run can recover “what remains” instead of only “what was decided.”

## Approximate token savings

In plain language: this usually aims to cut down the amount of repeated context you have to replay, not to eliminate it completely.

What we can say honestly from local validation:

- in favorable cases, the compact pack reduced replayed context by about `20%` to `55%`
- many real runs landed around `one-third to one-half less` repeated context
- if a workflow would otherwise need to replay about `1000` tokens of prior context, a reasonable expectation is often something more like `450` to `800` tokens instead

Examples from local validation:

- `401 -> 218` approximate tokens
- `312 -> 144` approximate tokens
- `290 -> 227` approximate tokens
- `337 -> 240` approximate tokens

Important: this is not a fixed guarantee per prompt. If the compact pack is not actually smaller than the source context, `codex-agent-mem` skips reinjection instead of pretending it saved tokens.

## What this prevents now

- losing the original objective after a few runs
- silently narrowing scope when the user asked for more
- declaring completion while pending work still exists
- forgetting blockers and re-entering the next run as if the task were finished

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
