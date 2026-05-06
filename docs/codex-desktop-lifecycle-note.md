# Codex Desktop Lifecycle Note

This note documents one practical boundary around `codex-agent-mem` when it runs inside long-lived Codex Desktop sessions.

## Short version

The strongest current diagnosis is:

- `codex-agent-mem` is not the sole root cause of the observed MCP accumulation and freeze behavior
- long-lived Codex Desktop lifecycle handling appears to be the main problem
- `codex-agent-mem` can still amplify the cost of that problem if the host keeps opening or retaining MCP processes

In other words:

`codex-agent-mem` needed runtime hardening. `v0.9.0` added the first defensive lifecycle layer, and `v1.0.0` adds lower-impact runtime modes, lazy initialization, compact responses, pack-hash reuse, heartbeat diagnostics, optional telemetry, and an optional daemon/stdio bridge. The broader Desktop lifecycle issue still sits above any one MCP.

## What was observed

In controlled checks with the same global MCP configuration:

- `codex exec --ephemeral` finished cleanly
- no comparable residual MCP accumulation was observed there

In the long-lived Codex Desktop app-server:

- multiple MCP roots remained alive across threads or workspace changes
- older workspace roots could still be observed after the active workspace had changed
- closed threads did not show clear cleanup
- idle time alone did not reliably remove all residual MCP stacks

That makes the working diagnosis much more about host lifecycle than about one repository or one MCP command.

## What this means for `codex-agent-mem`

`codex-agent-mem` still matters, even if it is not the primary cause.

If the host keeps too many MCP processes alive:

- every MCP adds process cost
- every MCP adds IPC overhead
- every MCP adds memory and handle pressure
- every MCP becomes part of the blast radius

So the right product response is not denial. It is defensive runtime behavior.

## What `v0.9.0` and `v1.0.0` harden

`v0.9.0` adds several runtime-facing defenses:

- `--sync-project-doc` is opt-in instead of default
- explicit `--idle-timeout-seconds`
- signal-aware shutdown
- explicit SQLite close
- lifecycle logging for stdio server start and exit
- `mem_health_runtime`
- SQLite defaults better suited to local multi-process pressure:
  - `WAL`
  - `busy_timeout`
  - `synchronous=NORMAL`
  - `temp_store=MEMORY`

These changes do not claim to fix Codex Desktop itself. They reduce unnecessary work, shorten orphan lifetime, and leave better evidence behind.

`v1.0.0` adds a lower-impact operating mode:

- `--profile minimal|standard|full`
- `--read-only`
- compact `content.text` responses with full data preserved in `structuredContent`
- lazy SQLite initialization for cheap unused connections
- `known_pack_hash` / `not_modified` for unchanged continuity packs
- heartbeat-based `same_db_process_count` and `spawn_storm_warning`
- optional bounded local telemetry
- optional `codex-agent-mem-daemon` plus stdio bridge mode

## Practical guidance today

Until the long-lived Desktop lifecycle is cleaner, the safest operating guidance is:

1. Keep the active MCP set as small as possible in Codex Desktop.
2. Prefer `codex exec --ephemeral` for controlled or long-running flows.
3. Keep `codex-agent-mem` on `v1.0.0` or newer when using Codex Desktop heavily.
4. Turn on `--sync-project-doc` only when you actually want automatic `AGENTS.md` reinjection.
5. Use `mem_health_runtime` when diagnosing process buildup.
6. Fully restart Codex Desktop if long-lived degradation returns.

## Scope of this note

This is an observed runtime diagnosis, not a blanket claim about every Codex Desktop build or every host environment.

It exists because the distinction matters:

- a host-side lifecycle issue should not be misreported as “this MCP is the cause”
- at the same time, MCPs still need to degrade well when the host behaves badly

That second responsibility is part of `codex-agent-mem` itself, and `v1.0` continues in that direction with stronger observability and lower-impact runtime modes.
