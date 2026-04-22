# AGENTS

This repository is intentionally optimized for coding agents, deep-research tools, and maintainers who need a fast map of what exists today.

## Public name vs import name

- Public repository name: `codex-agent-mem`
- Python package import name: `codex_agent_mem`
- CLI commands use the public name with hyphens, for example `codex-agent-mem-smoke`

## What this project is

- A portable, local-first memory layer for Codex and adjacent agent workflows
- Current durable store: local SQLite
- Current retrieval surface: MCP stdio
- Current capture path: Codex `notify` on `agent-turn-complete`
- Current inspection surface: local FastAPI UI at `/ui`
- Current continuity surface: generated `AGENTS.md` working-memory block when compression is favorable
- Current extraction strategy: heuristic `session_summary` and `decision` extraction

## codex-agent-mem Operational Continuity

- Use the `codex-agent-mem` MCP as the source of operational continuity for this repository.
- The user should not need to remind Codex to use `codex-agent-mem`; apply it proactively when it reduces repeated context, prevents false completion, or improves continuity.
- At the start of a task, call `mem_context_pack` with project key `codex-agent-mem` when previous context may matter.
- If a prior pack hash is known, pass it as `known_pack_hash`; if the tool returns `not_modified=true`, do not repeat or summarize the same context.
- During work, use `mem_search` only when the compact pack is insufficient.
- Before claiming completion, call `mem_open_work` and `mem_completion_check`.
- If pending work, blockers, or DoD gaps remain, do not claim the task is complete.
- Do not invent memory state. If the MCP is unavailable or the project is not found, say so explicitly.

## What this project is not yet

- Not an embeddings or vector database platform
- Not a full analytics UI product
- Not an App Server capture layer
- Not a hooks-based Codex integration
- Not a multi-agent orchestration framework

## Fastest commands

```powershell
pip install -e .[dev]
pytest -q
python -m compileall src
ruff check .
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
python -m build
```

## Repository map

- `src/codex_agent_mem/`
  Core package code
- `tests/`
  Executable tests for API, MCP, ingest, notify, and smoke flow
- `examples/codex/`
  Codex config examples and optional HTTP notify wrapper
- `scripts/`
  Windows and POSIX bootstrap helpers
- `docs/`
  Quickstart, integration notes, architecture, support matrix, and design decisions

## Key files

- `src/codex_agent_mem/api.py`
  FastAPI inspection API
- `src/codex_agent_mem/mcp_stdio.py`
  MCP stdio server
- `src/codex_agent_mem/codex_notify.py`
  Codex notify adapter
- `src/codex_agent_mem/db.py`
  SQLite persistence and query surface
- `src/codex_agent_mem/schema.sql`
  Database schema
- `src/codex_agent_mem/bootstrap_codex.py`
  Codex config snippet generator
- `src/codex_agent_mem/project_doc.py`
  Generated AGENTS block sync for compressed continuity
- `src/codex_agent_mem/context_pack.py`
  Compact working-memory pack builder and token-budget stats
- `src/codex_agent_mem/smoke.py`
  End-to-end smoke verification

## Read this before editing

- Keep the current release line narrow and honest
- Do not document deferred areas as implemented
- Preserve the distinction between public repo naming and Python import naming
- Prefer deterministic persistence before adding semantic enrichment
- Keep examples copy-pasteable on Windows

## Documentation map

- `README.md`
  Public entry point
- `docs/quickstart.md`
  Fastest operational path
- `docs/codex-integration.md`
  Notify + MCP integration details
- `docs/support-matrix.md`
  Supported and unsupported combinations
- `docs/design-decisions.md`
  Product and architecture decisions
- `docs/discoverability.md`
  Suggested GitHub description, topics, and release framing

## Contribution expectations

- Run `ruff check .`
- Run `python -m compileall src`
- Run `pytest -q`
- If packaging or install flow changed, run `python -m build`
- If Codex integration changed, rerun `codex-agent-mem-smoke`
