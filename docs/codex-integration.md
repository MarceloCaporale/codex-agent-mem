# Codex Integration

`codex-agent-mem` integrates with Codex using two runtime surfaces:

1. `notify` for turn capture
2. MCP stdio for retrieval

It also exposes a local FastAPI inspector for humans:

3. `/ui` for project, session, turn, and observation browsing

And it can reinject compressed continuity when enabled:

4. optional `AGENTS.md` sync for generated working memory when the pack is smaller than the source context

And it now exposes explicit audit and persistence utilities:

5. provenance, health, and snapshot tools for debugging derived state without mutating raw history

And on top of that, it now supports governed memory selection:

6. policies, inheritance links, and repair flows to keep continuity explicit instead of silently mixing memory

## Capture flow

- Codex emits `agent-turn-complete`
- `codex_agent_mem.codex_notify` normalizes the payload
- the event is persisted into local SQLite
- heuristic extraction produces `session_summary`, `decision`, and operational-state observations
- the store derives operational state from those observations: objective, constraints, pending items, completed items, blockers, and completion claims
- the store compiles a working-memory pack from recent turns, durable decisions, and operational state
- when that pack is smaller than the source context and reinjection is enabled, `AGENTS.md` is updated in the working directory
- every generated pack event is recorded as a context sync metric for later inspection
- observation provenance, health reports, and snapshot events are persisted for later audit
- project policies, inheritance links, and repair events are also persisted so continuity selection stays explainable

## Retrieval flow

- Codex connects to the MCP server
- the MCP server exposes:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
  - `mem_open_work`
  - `mem_completion_check`
  - `mem_recent_changes`
  - `mem_scope_guard`
  - `mem_context_pack`
  - `mem_provenance`
  - `mem_health`
  - `mem_health_runtime`
  - `mem_snapshot_list`
  - `mem_snapshot_create`
  - `mem_snapshot_restore`
  - `mem_policy_list`
  - `mem_policy_validate`
  - `mem_policy_add`
  - `mem_policy_remove`
  - `mem_inheritance_list`
  - `mem_inheritance_add`
  - `mem_inheritance_remove`
  - `mem_repair_propose`
  - `mem_repair_apply`

`mem_context_pack` also supports `budget=auto`, so the runtime can select the smallest fitting reinjection profile instead of always forcing one fixed budget.

## Generate the config snippet

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

The generated config uses:

- `notify`
- `[mcp_servers."codex-agent-mem"]`
- `--idle-timeout-seconds` for defensive stdio cleanup
- per-tool `approval_mode = "approve"` for the read-only retrieval tools
- Python module targets under `codex_agent_mem`
- snapshot, audit, and read-only governance tools approved alongside the continuity tools

`--sync-project-doc` is now opt-in. Add it to `notify` only if you want automatic `AGENTS.md` reinjection in the working directory.

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

## POSIX note

On macOS and Linux, prefer:

- `$HOME/.codex_agent_mem/codex_agent_mem.db` for the local database path
- normal bash/zsh quoting, for example:

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

When editing `~/.codex/config.toml` manually, use the installed command paths from your environment instead of Windows-style `Scripts\\` paths.

## Optional HTTP ingest

The default and simplest path is direct DB ingestion through `notify`.

An optional HTTP wrapper also exists:

- [examples/codex/notify_writer.py](../examples/codex/notify_writer.py)

That path is useful only if you explicitly want `notify -> HTTP -> local API`.

## MCP lifecycle note

The current transport is stdio. That means one MCP process per host connection is expected; this integration does not claim a singleton daemon. `codex-agent-mem` now adds an idle timeout, signal-aware shutdown, runtime diagnostics, and explicit SQLite cleanup so unused or orphaned stdio instances exit more defensively.

## Current limits

- no one-click GitHub MCP install
- no Codex hooks adapter yet
- no Codex App Server adapter yet
- no automatic semantic memory layer
- AGENTS sync is intentionally skipped when the generated pack is not smaller than the source context
- operational state is still heuristic and derived from turn text, not from a dedicated planner protocol
- provenance is authoritative only for persisted payload/turn/session context that this capture path can actually see
