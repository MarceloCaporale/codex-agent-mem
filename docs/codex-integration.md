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

For low-impact Desktop and long-running hosts, v1.0 also adds:

7. read-only MCP mode, profile-based tool surfaces, compact responses, lazy SQLite initialization, pack-hash reuse, runtime heartbeat diagnostics, optional telemetry, and an optional local daemon/stdio bridge

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
  - `mem_session_list`
  - `mem_scope_resolve`
  - `mem_bootstrap_context`
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
  - `mem_note_create`
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

At task startup, prefer `mem_bootstrap_context(project_key, ...)` when the
host can provide a chat title, thread hint, cwd, repo path, or mentioned files.
It is read-only and refuses to treat a project-wide container pack as active
context when the stored memory has several candidate lanes. If the scope is
already explicit, call `mem_context_pack(project_key, session_id=...)`.

`mem_context_pack` also supports `budget=auto`, so the runtime can select the smallest fitting reinjection profile instead of always forcing one fixed budget.

In v1.0, `mem_context_pack` also returns a stable `pack_hash` and accepts `known_pack_hash`. If the generated continuity pack did not change, the server can return a compact `not_modified=true` response instead of resending the full pack.

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
- `--profile` for profile-aware tool surfaces
- `--response-mode` for compact, balanced, or verbose MCP text responses
- per-tool `approval_mode = "approve"` for the configured MCP tools
- Python module targets under `codex_agent_mem`
- snapshot, audit, and governance tools approved alongside the continuity tools

The default helper emits the `full` profile. That keeps writable continuity
available, including manual notes, snapshots, governance, repairs, and restore
tools. Review the approved tools before pasting if you want a narrower surface.

For an explicit retrieval-only audit/debug profile, generate:

```bash
codex-agent-mem-bootstrap-codex --mcp-profile minimal --mcp-read-only
```

```powershell
codex-agent-mem-bootstrap-codex --mcp-profile minimal --mcp-read-only
```

That exposes only:

- `mem_session_list`
- `mem_scope_resolve`
- `mem_bootstrap_context`
- `mem_context_pack`
- `mem_open_work`
- `mem_completion_check`
- `mem_health_runtime`

and disables mutating MCP tools.

`--sync-project-doc` is now opt-in. Add it to `notify` only if you want automatic `AGENTS.md` reinjection in the working directory.

## MCP tool approvals

The generated snippet also marks the configured MCP tools as:

```toml
approval_mode = "approve"
```

That matters for non-interactive Codex runs such as `codex exec`, where MCP tool prompts can otherwise be cancelled before returning data.

## Windows note

Use single-quoted TOML strings so backslashes stay literal.

See:

- [examples/codex/config.toml.example](../examples/codex/config.toml.example)
- [examples/codex/config.read-only-audit.example.toml](../examples/codex/config.read-only-audit.example.toml)

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

## Codex Desktop lifecycle note

Current evidence points to a host-side lifecycle problem in long-lived Codex Desktop sessions rather than a single MCP being the sole root cause.

Observed pattern:

- `codex exec --ephemeral` with the same global MCP config finishes cleanly
- the long-lived Codex Desktop app-server can retain multiple MCP roots across threads or workspace changes
- that makes every active MCP more expensive when the host stops reusing or cleaning them properly

What `codex-agent-mem` does about it:

- makes `--sync-project-doc` opt-in instead of default
- adds an explicit stdio idle timeout
- adds signal-aware shutdown and explicit SQLite close
- reports runtime state through `mem_health_runtime`
- hardens SQLite defaults for concurrent local use
- supports `--profile minimal --read-only` for retrieval-only Desktop checks
- avoids opening SQLite for `initialize`, `tools/list`, and `mem_health_runtime`
- avoids resending unchanged context packs when `known_pack_hash` matches
- can run behind an optional local daemon if the host opens many stdio connections

## Optional daemon mode

Stdio remains the default and most compatible transport.

If a host repeatedly opens MCP stdio connections, you can run a local daemon:

```bash
codex-agent-mem-daemon --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db" --profile full --auth-token YOUR_LOCAL_TOKEN
```

Then point the stdio bridge at it:

```bash
codex-agent-mem-mcp --daemon-url http://127.0.0.1:37773 --daemon-token YOUR_LOCAL_TOKEN --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

On Windows PowerShell:

```powershell
codex-agent-mem-daemon --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --profile full --auth-token YOUR_LOCAL_TOKEN
codex-agent-mem-mcp --daemon-url http://127.0.0.1:37773 --daemon-token YOUR_LOCAL_TOKEN --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

The public `1.0.x` daemon accepts only loopback bind hosts (`127.0.0.1`, `localhost`, or `::1`). The optional bearer token is recommended when the daemon is kept alive, but it is a local safeguard only; it does not replace TLS, OAuth, hosted authentication, or a remote access-control layer.

That does not claim to fix the host bug. It reduces the blast radius and makes the MCP easier to audit.

For the full diagnostic note and temporary mitigations, see:

- [Codex Desktop Lifecycle Note](./codex-desktop-lifecycle-note.md)

## Current limits

- no one-click GitHub MCP install
- no Codex hooks adapter yet
- no Codex App Server adapter yet
- no automatic semantic memory layer
- no encrypted-at-rest SQLite database in the public `1.0.x` line
- AGENTS sync is intentionally skipped when the generated pack is not smaller than the source context
- operational state is still heuristic and derived from turn text, not from a dedicated planner protocol
- provenance is authoritative only for persisted payload/turn/session context that this capture path can actually see
