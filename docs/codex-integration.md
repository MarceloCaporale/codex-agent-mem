# Codex Integration

`codex-agent-mem` integrates with Codex using two runtime surfaces:

1. `notify` for turn capture
2. MCP stdio for retrieval

It also exposes a local FastAPI inspector for humans:

3. `/ui` for project, session, turn, and observation browsing

And it can reinject compressed continuity automatically:

4. `AGENTS.md` sync for generated working memory when the pack is smaller than the source context

## Capture flow

- Codex emits `agent-turn-complete`
- `codex_agent_mem.codex_notify` normalizes the payload
- the event is persisted into local SQLite
- heuristic extraction produces `session_summary` and `decision` observations
- the store compiles a working-memory pack from recent turns and durable decisions
- when that pack is smaller than the source context, `AGENTS.md` is updated in the working directory

## Retrieval flow

- Codex connects to the MCP server
- the MCP server exposes:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
  - `mem_context_pack`

## Generate the config snippet

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

The generated config uses:

- `notify`
- `[mcp_servers."codex-agent-mem"]`
- `--sync-project-doc`
- per-tool `approval_mode = "approve"` for the read-only retrieval tools
- Python module targets under `codex_agent_mem`

## MCP tool approvals

The generated snippet also marks the read-only retrieval tools as:

```toml
approval_mode = "approve"
```

That matters for non-interactive Codex runs such as `codex exec`, where MCP tool prompts can otherwise be cancelled before returning data.

## Windows note

Use single-quoted TOML strings so backslashes stay literal.

See:

- [examples/codex/config.toml.example](../examples/codex/config.toml.example)

## Optional HTTP ingest

The default and simplest path is direct DB ingestion through `notify`.

An optional HTTP wrapper also exists:

- [examples/codex/notify_writer.py](../examples/codex/notify_writer.py)

That path is useful only if you explicitly want `notify -> HTTP -> local API`.

## Current limits

- no one-click GitHub MCP install
- no Codex hooks adapter yet
- no Codex App Server adapter yet
- no automatic semantic memory layer
- AGENTS sync is intentionally skipped when the generated pack is not smaller than the source context
