# AGENTS

This repository is intentionally optimized for MCP-compatible AI agents, coding workflows, deep-research tools, and maintainers who need a fast map of what exists today.

## Public name vs import name

- Public repository name: `codex-agent-mem`
- Python package import name: `codex_agent_mem`
- CLI commands use the public name with hyphens, for example `codex-agent-mem-smoke`

## What this project is

- A portable, local-first MCP memory layer for agent continuity across MCP-compatible runtimes
- Current durable store: local SQLite
- Current retrieval surface: MCP stdio
- Current capture path: local agent turn ingestion, including Codex `notify` on `agent-turn-complete`
- Current inspection surface: local FastAPI UI at `/ui`
- Current continuity surface: generated `AGENTS.md` working-memory block when compression is favorable
- Current extraction strategy: heuristic extraction of session summaries, user requests, objectives, decisions, constraints, pending/completed work, blockers, DoD items, and completion claims

## Working rules for agents

- Preserve the local-first MCP core.
- Do not use an operational maintainer database for tests; use temporary databases.
- Keep hosted/web bridge experiments out of the public core unless the repository scope changes explicitly.
- Keep compatibility and token-savings claims tied to reproducible evidence.
- Keep the six README files equivalent in content across languages.
- For broad/container project keys, prefer `mem_bootstrap_context` or `mem_scope_resolve` before loading `mem_context_pack(project_key)`. A project-wide pack may remain available, but it must not be treated as the active thread when candidate lanes are ambiguous.
- Do not tag, publish, or release from a dirty tree.

## Fastest commands

```powershell
pip install -e .[dev]
pytest -q
python -m compileall src
ruff check .
python scripts/mcp_contract_smoke.py --both
python scripts/check_repo_hygiene.py
python scripts/smoke_release.py --mcp-subprocess --with-ruff --with-build --with-wheel-smoke
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

- Keep the current release line portable, local-first, and evidence-based
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
- `docs/validation/`
  Validation levels, client behavior, and runtime evidence
- `docs/benchmarks/`
  Reproducible token-savings methodology
- `docs/design-decisions.md`
  Product and architecture decisions
- `docs/discoverability.md`
  Suggested GitHub description, topics, and release framing

## Contribution expectations

- Run `ruff check .`
- Run `python -m compileall src`
- Run `pytest -q`
- Run `python scripts/mcp_contract_smoke.py --both` for MCP contract changes
- Run `python scripts/check_repo_hygiene.py` before release review
- If packaging or install flow changed, run `python -m build`
- If Codex integration changed, rerun `codex-agent-mem-smoke`
