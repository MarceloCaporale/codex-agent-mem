# Kimi Code CLI Evidence - v1.0.1

Evidence level: L2 connection validation.

| Field | Value |
| --- | --- |
| Date | 2026-04-26 |
| OS | Windows local validation environment |
| Client/runtime | Kimi Code CLI 1.38.0 |
| Model/backend | Kimi Code CLI connection test; no full model tool-call validation claimed |
| MCP profile | `standard` |
| Read-only | `true`; connection/tool-listing evidence only, not writable continuity |
| Response mode | `compact` |
| Tools called | Tool listing / connection test |
| Observed structuredContent shape | Not claimed beyond connection and tool listing |
| Runtime health | MCP server connected and listed the expected standard-profile tools |
| Caveat | This is connection/tool-listing evidence only |
| Result | PASS for connection validation |

Summary:

- Kimi Code CLI connected to the `codex-agent-mem` MCP server through stdio.
- Full live model tool-call validation is not claimed for Kimi models in v1.0.1.
