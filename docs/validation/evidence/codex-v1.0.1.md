# Codex Evidence - v1.0.1

Evidence level: L3-R retrieval-only plus L1 fixtures.

| Field | Value |
| --- | --- |
| Date | 2026-04-26 |
| OS | Windows local validation environment |
| Client/runtime | Codex CLI/Desktop MCP stdio paths |
| Model/backend | Codex/GPT workflow; model details tracked in private validation notes |
| MCP profile | `minimal` for public fixtures; `full` for a retrieval-only live surface check |
| Read-only | `true` for this historical MCP retrieval validation; this note does not validate writable continuity |
| Response mode | `compact` |
| Tools called | `mem_health_runtime`, `mem_context_pack`, `mem_policy_list`, `mem_snapshot_list`, `mem_inheritance_list`, `mem_repair_propose`, `mem_recent`, plus read-only mutation-block check |
| Observed structuredContent shape | Context pack object with `pack_hash`; list tools as object roots shaped `{items, count}` |
| Runtime health | `server_version=1.0.1`, stable process state, request counter increased during calls |
| Caveat | Long-lived and short-lived Codex hosts can differ in lifecycle; guidance is documented in the support matrix |
| Result | PASS |

Summary:

- `mem_context_pack` returned a continuity pack with `pack_hash`.
- Repeating `mem_context_pack` with `known_pack_hash` returned
  `not_modified=true`.
- Mutating tools were blocked in read-only mode.
- Writable manual-note continuity is validated separately in
  `manual-notes-runtime-v1.0.1.md`.
