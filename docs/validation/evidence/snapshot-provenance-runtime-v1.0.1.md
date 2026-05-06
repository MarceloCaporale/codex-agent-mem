# Snapshot Provenance Runtime Evidence - v1.0.1

Date: 2026-04-29

Evidence level: L3-W writable snapshot-provenance bridge smoke.

## Scope

Runtime validation for the local `codex-agent-mem` installation used by Codex,
Gemini, and Claude bridges. This public evidence note omits local paths and
operational database details; exact local evidence is kept outside public docs.

## Installation Update

The local package was reinstalled from the v1.0.1 hotfix worktree into the local
bridge runtime environment.

Installed package verification:

```text
codex-agent-mem version: 1.0.1
CodexAgentMemStore.snapshot_create(self, project_key, label, *, session_id=None)
```

## Daemon Runtime Health

After reinstall, the local MCP daemons were restarted.

```text
Codex  profile=full response_mode=compact read_only=false
Gemini profile=full response_mode=verbose read_only=false
Claude profile=full response_mode=compact read_only=false
```

All three health checks reported `server_version=1.0.1`,
`spawn_storm_warning=false`, and one active process per database.

## Scoped Snapshot Smoke

A persisted `codex-agent-mem` session was selected through `mem_session_list`.
`mem_snapshot_create` was called with the internal MCP `session_id`.

Result:

```text
snapshot created with session_id set
external_session_id present
provenance_confidence=high
```

The same snapshot was listed successfully through Codex, Gemini, and Claude
daemon endpoints with consistent `session_id` and high-confidence provenance.

## Unscoped Snapshot Smoke

`mem_snapshot_create` was called without `session_id`.

Result:

```text
session_id=null
external_session_id=null
provenance_confidence=low
provenance_warning present=true
```

`mem_snapshot_list` returned the same unscoped provenance.

## Result

PASS.

The local installation no longer attaches snapshots without `session_id` to the
latest project turn. Explicit session-scoped snapshots are visible from Codex,
Gemini, and Claude daemon endpoints with consistent provenance.
