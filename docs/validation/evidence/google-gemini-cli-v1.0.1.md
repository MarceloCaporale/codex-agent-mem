# Google Gemini CLI Evidence - v1.0.1

Evidence level: L3-R retrieval-only with client-exposure caveat.

| Field | Value |
| --- | --- |
| Date | 2026-04-26 |
| OS | Windows local validation environment |
| Client/runtime | Google Gemini CLI MCP stdio |
| Model/backend | Gemini CLI session; exact model tracked in private validation notes |
| MCP profile | `standard` |
| Read-only | `true`; this note validates retrieval behavior, not writable continuity |
| Response mode | `compact` for core contract check; `verbose` when compact only exposed short summaries to the agent |
| Tools called | `mem_health_runtime`, `mem_context_pack`, `mem_policy_list` |
| Observed structuredContent shape | Core MCP payload is structured; verbose mode rendered useful continuity payload into `content.text` |
| Runtime health | `server_version=1.0.1`, stable process, request counter increased |
| Caveat | Some Google Gemini CLI flows do not expose useful `structuredContent` to the model in compact mode |
| Result | PASS with response-mode guidance |

Summary:

- Google Gemini CLI detected the `codex-agent-mem` MCP tools.
- Compact mode can expose only short text summaries to the model in some client
  flows.
- `response_mode=verbose` exposed the continuity pack payload usefully to the
  agent.
