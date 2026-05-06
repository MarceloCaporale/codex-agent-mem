# Qwen Code / Ollama Evidence - v1.0.1

Evidence level: L3-R retrieval-only.

| Field | Value |
| --- | --- |
| Date | 2026-04-26 |
| OS | Windows local validation environment |
| Client/runtime | Qwen Code 0.15.0 with local Ollama-backed models |
| Model/backend | `qwen3.6:latest`; local Qwen model smokes also covered `qwen3.6:35b-a3b-q8_0` and `qwen3.5:9b` |
| MCP profile | `standard` |
| Read-only | `true`; this note validates retrieval behavior, not writable continuity |
| Response mode | `compact` |
| Tools called | `mem_context_pack`, `mem_search`, `mem_open_work`, `mem_completion_check`, `mem_health_runtime` |
| Observed structuredContent shape | Context pack object with `pack_hash`; search/list payloads exposed as object roots where visible |
| Runtime health | `server_version=1.0.1`, request counter increased, `spawn_storm_warning=false`, `not_modified=true` observed |
| Caveat | This is an MCP-capable local workflow, not a native Ollama adapter in the public core |
| Result | PASS |

Summary:

- Real MCP calls were made from a named local client/runtime.
- Runtime remained stable in retrieval-only mode.
- Repeated context-pack calls supported `not_modified=true`.
