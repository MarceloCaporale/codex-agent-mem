# Manual Operational Notes Verification - v1.0.1

Date: 2026-04-29

## Finding

Writable MCP mode existed, but the public tool surface did not provide a direct
tool for "store this operational note now as searchable memory." Using
snapshots for that job would blur two separate contracts:

- snapshot: versioned state capture for audit, restore, or checkpointing;
- note: indexed operational memory meant for retrieval and continuity.

## Fix

`mem_note_create(project_key, text, session_id?, title?, tags?, importance?)`
was added as the explicit writable note path.

Contract:

- validates `project_key`;
- validates that optional `session_id` belongs to `project_key`;
- stores the note as an indexed observation with `source_kind=manual_note`;
- records provenance without inventing a session when `session_id` is omitted;
- returns `observation_id`, session provenance, tags, importance, and creation
  status;
- is blocked when the MCP runtime is started with `read_only=true`.

`project_key` must already exist. In normal use it is created by the notify,
ingest, smoke, or prior capture path before manual notes are added. If
`session_id` is supplied, it must belong to that project.

Unscoped notes are project-scoped. They are not attached to the latest turn by
inference.

## Verification

In-repository validation covers:

- direct store write -> `mem_search` exact phrase retrieval;
- direct store write -> `mem_context_pack(..., budget="full", session_id=...)`
  inclusion;
- provenance inspection through `mem_provenance`;
- cross-project `session_id` rejection;
- MCP `tools/list` exposure in `full` profile;
- MCP `mem_note_create` -> `mem_search` -> `mem_context_pack`;
- MCP subprocess A `mem_note_create` -> subprocess B `mem_search` /
  `mem_context_pack` over the same temporary SQLite database;
- read-only rejection;
- `scripts/mcp_contract_smoke.py --both`.

## Public Boundary

This verification uses synthetic project keys and synthetic note text. It does
not require private local paths, real chat IDs, credentials, or operational DB
content.
