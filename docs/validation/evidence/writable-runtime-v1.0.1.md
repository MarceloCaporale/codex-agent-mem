# Writable Runtime Evidence - v1.0.1

Date: 2026-04-29

## Scope

Public evidence note for the writable MCP runtime contract. This note is
sanitized: it omits local filesystem paths, private database paths, credentials,
and operational memory contents.

## Runtime Contract

Normal continuity installations should run with `read_only=false` when agents
are expected to persist manual operational notes, snapshots, closure events,
governance state, or repair events through MCP tools.

`--read-only` remains supported, but it is an explicit retrieval-only
audit/debug mode that blocks mutating tools.

## Evidence

The contract smoke was run in both in-process and subprocess modes against a
temporary SQLite database.

Observed behavior:

```text
profile=full
response_mode=compact
read_only=false
mem_note_create(project_key, text, session_id, tags, importance) succeeded
source_kind=manual_note
mem_search found the manual note by exact phrase
mem_context_pack included the manual note in the continuity pack
later MCP subprocess reopened the same SQLite database
later mem_search found the same manual note by exact phrase
later mem_context_pack included the same manual note
later known_pack_hash repeat returned not_modified=true
mem_snapshot_create(project_key, label, session_id) succeeded
provenance_confidence=high
provenance_warning=null
mem_snapshot_list returned the created snapshot
```

Focused tests still cover explicit read-only mutation blocking.

## Result

PASS.

The public smoke now verifies the writable operational-memory path as the normal
MCP contract while retaining explicit read-only safety coverage elsewhere.
