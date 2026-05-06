# Claude Code Evidence - v1.0.1

Evidence level: L3-R retrieval-only.

| Field | Value |
| --- | --- |
| Date | 2026-04-26 / 2026-04-27 session-aware smoke |
| OS | Windows local validation environment |
| Client/runtime | Claude Code MCP stdio |
| Model/backend | Claude Code session; exact model tracked in private validation notes |
| MCP profile | `standard` |
| Read-only | `true`; this note validates retrieval behavior, not writable continuity |
| Response mode | `compact` |
| Tools called | `mem_health_runtime`, `mem_session_list`, `mem_context_pack`, `mem_open_work`, `mem_completion_check`, list tools including policy/snapshot/inheritance/repair listings |
| Observed structuredContent shape | Context pack object with text/stats/operational state; list tools including `mem_session_list` as `{items, count}` |
| Runtime health | `server_version=1.0.1`, stable PID, `spawn_storm_warning=false`, request counter increased |
| Caveat | Claude Code exposes the useful session metadata through `structuredContent.stats`; in this smoke it did not surface the server's raw compact `content[0].text` breadcrumbs to the model. |
| Result | PASS |

Summary:

- Claude Code detected the `codex-agent-mem` MCP tools.
- `mem_context_pack` returned useful structured continuity data in compact mode.
- Repeating the same pack request with `known_pack_hash` returned
  `not_modified=true`.
- Post session-aware retrieval smoke confirmed `mem_session_list`, scoped
  `mem_context_pack(project_key, session_id)`, `session_filter_applied=true`,
  `source_session_count=1`, and unscoped packs with multiple source sessions.
- Direct daemon verification confirmed the server emits compact `content.text`
  lines with `session_filter=applied` for scoped packs and a
  `mem_session_list + session_id` hint for broad unscoped packs. Claude Code's
  model-visible summary for this smoke surfaced the same facts through
  `structuredContent.stats`, not through raw `content[0].text`.
