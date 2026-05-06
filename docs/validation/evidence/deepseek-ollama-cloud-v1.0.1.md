# DeepSeek via Ollama Cloud Evidence - v1.0.1

Evidence level: L3-R retrieval-only.

| Field | Value |
| --- | --- |
| Date | 2026-04-26 |
| OS | Windows local validation environment |
| Client/runtime | Qwen Code 0.15.0 using an MCP-capable local workflow |
| Model/backend | `deepseek-v3.2:cloud` through Ollama Cloud |
| MCP profile | `standard` |
| Read-only | `true`; this note validates retrieval behavior, not writable continuity |
| Response mode | `compact` |
| Tools called | `mem_context_pack`, `mem_search`, `mem_health_runtime` |
| Observed structuredContent shape | Context pack object with `pack_hash`; search payload visible through the MCP client path |
| Runtime health | `server_version=1.0.1`, requests increased, `spawn_storm_warning=false`, `not_modified=true` observed |
| Caveat | This is not a hosted bridge in the public core; it is a cloud-backed model workflow reached through a local MCP-capable client |
| Result | PASS |

Summary:

- Real MCP calls covered context-pack retrieval, search, and runtime health.
- Runtime stayed stable in retrieval-only mode during the observed validation.
