# Manual Notes Runtime Evidence - v1.0.1

Date: 2026-04-29

Evidence level: L3-W writable continuity bridge smoke.

## Scope

Local Windows runtime validation for the explicit manual operational memory
write path.

Clients exercised through their local MCP bridge profiles:

- Codex bridge: `profile=full`, `read_only=false`, `response_mode=compact`
- Gemini bridge: `profile=full`, `read_only=false`, `response_mode=verbose`
- Claude bridge: `profile=full`, `read_only=false`, `response_mode=compact`

## Tools Called

For each bridge:

1. `tools/list`
2. `mem_health_runtime`
3. `mem_note_create`
4. `mem_search`
5. `mem_context_pack`

## Result

All three bridges exposed `mem_note_create` after the local install and daemon
restart.

For each bridge, a synthetic manual note was created under a synthetic project
and scoped to that bridge's synthetic session. The note result reported:

- `source_kind=manual_note`
- the expected internal `session_id`
- `profile=full`
- `read_only=false`

`mem_search` found the exact phrase for each created note, and
`mem_context_pack(project_key, budget="full", session_id=...)` included the
same phrase in the returned pack text.

The release gate also verifies that a manual note created through MCP in one
subprocess remains retrievable from a later MCP subprocess over the same
temporary SQLite database.

## Boundary

The runtime smoke used synthetic project/session labels and synthetic note
phrases. This public evidence omits local filesystem paths, real chat IDs,
database paths, and exact local observation IDs.
