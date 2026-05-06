# Support Matrix

This matrix separates the MCP core contract from client-specific behavior. The
core server returns full payloads in `structuredContent`; each client decides how
much of that payload is exposed to the model in its own UI/runtime.

## Runtime and platform support

| Area | Status | Notes |
| --- | --- | --- |
| Windows local development | Supported | Primary practical target today. |
| Linux CI | Supported | Covered in GitHub Actions. |
| Windows CI | Supported | Covered in GitHub Actions. |
| macOS local development | Expected | No CI coverage yet. |
| Public support level | Supported local-first core | The `1.0.x` line has no hosted service or formal SLA. |
| Local SQLite persistence | Supported | Plaintext by default; treat the DB as sensitive project data. |
| MCP stdio retrieval | Supported | Current primary retrieval surface. |
| Optional local daemon | Supported | Loopback-only in `1.0.x`; remote daemon bind is intentionally rejected. |
| Optional daemon bearer token | Supported | Protects local `/mcp`; this is not hosted auth, OAuth, or TLS. |
| Daemon `/health` | Supported | Sanitized runtime metadata; use `mem_health_runtime` through MCP for detailed state. |
| FastAPI inspection API/UI | Supported | Local inspection at `/ui`. |
| Prompt-injection hardening | Basic guardrail | Retrieved memory is marked as advisory project context, not higher-priority instruction. |
| Local SQLite database encryption | Not built in | Use OS/user-profile or volume encryption if needed. |

## Client/runtime evidence

Evidence levels:

- `L0`: code/package contract only.
- `L1`: automated fixture or local smoke.
- `L2`: real local MCP server/daemon path exercised outside pure unit tests.
- `L3-R`: named client/runtime made live retrieval or diagnostic MCP tool calls with mutability mode declared.
- `L3-W`: named client/runtime demonstrated writable continuity with `read_only=false`.
- `L4`: external protocol-level compatibility review without live model tool-call validation.

| Client/runtime | Recommended mode | Evidence level | v1.0.1 result | Notes |
| --- | --- | --- | --- | --- |
| Codex CLI / Codex Desktop | `response_mode=compact` | L3-R plus L3-W bridge smoke and L1 fixtures | Validated | Compact text plus full `structuredContent` is usable; writable continuity is covered by bridge smoke evidence. |
| Claude Code | `response_mode=compact` | L3-R plus L3-W bridge smoke | Validated | Live retrieval calls observed object-root list payloads and context packs; writable continuity is covered by bridge smoke evidence. |
| Google Gemini CLI | `response_mode=verbose` when compact only exposes summaries | L3-R plus L3-W bridge smoke | Validated with configuration caveat | The core MCP payload is valid, but Gemini may not expose useful `structuredContent` to the model in compact mode. Use verbose if the model only sees a one-line summary. |
| Google Antigravity | Same guidance as Google Gemini CLI when using the same MCP bridge behavior | L0 unless directly validated | Configuration-dependent | Document separately if validated directly in a release run. |
| Qwen Code / Ollama workflow | Client-appropriate MCP mode | L3-R | Validated as retrieval-only workflow | This is not a native Ollama adapter; it is an MCP-capable local workflow. |
| DeepSeek / Minimax via Ollama Cloud workflow | Client-appropriate MCP mode | L3-R | Validated as retrieval-only workflow | This is not a native hosted bridge in the public core. |
| Kimi Code CLI | Client-appropriate MCP mode | L2 connection validation | Connection documented | Treat as MCP-client connection validation, not a separate backend feature or full model-run claim. |

Public evidence notes for validated rows live under
[docs/validation/evidence](./validation/evidence/README.md). Evidence files
summarize the observed client/runtime, mode, tools, limits, and caveats without
publishing private transcripts or operational database contents.

## MCP response behavior

| Surface | Status | Notes |
| --- | --- | --- |
| `structuredContent` | Canonical payload | Full tool result for MCP clients that expose structured payloads. |
| List results in `structuredContent` | Object-root contract | Lists are wrapped as `{items, count}` for stricter MCP clients. |
| Session list results | Object-root contract | `mem_session_list` returns `{items, count}` for recent persisted sessions in one project. |
| Startup scope resolution | Object-root contract | `mem_scope_resolve` and `mem_bootstrap_context` return candidate lanes and defensive next actions before a broad pack is treated as active context. |
| `content.text` compact | Supported default | Short human-readable summary for low-token clients. |
| `content.text` balanced | Supported | Summary plus notice that complete data is in `structuredContent`. |
| `content.text` verbose | Supported | JSON text view for clients that do not expose `structuredContent` usefully. |
| `pack_hash` / `known_pack_hash` | Supported | Enables unchanged-pack `not_modified` responses. |
| `session_id` retrieval filter | Supported | Optional retrieval filter for persisted memory inside a `project_key`; not live current-turn awareness. |

## Tool and feature support

| Feature | Status | Notes |
| --- | --- | --- |
| `mem_context_pack` compact retrieval | Supported | Returns compressed continuity pack and approximate token budget. |
| `mem_session_list` | Supported | Lists recent persisted sessions/chats so broad project scopes can be narrowed. |
| `mem_scope_resolve` | Supported | Read-only resolver for explicit thread/path/query hints; does not infer live current-turn state. |
| `mem_bootstrap_context` | Supported | Read-only startup helper that returns a scoped pack only when `session_id` is explicit, otherwise returns candidate lanes and narrowing guidance. |
| `mem_context_pack` auto budget | Supported | Selects `micro`, `normal`, or `full`. |
| `mem_recent_changes` | Supported | Summarizes deltas since the last meaningful continuity baseline. |
| `mem_scope_guard` | Supported | Exposes must-not-drop scope, constraints, and closure conflicts. |
| `mem_open_work` / `mem_completion_check` | Supported | Deterministic closure control. |
| `mem_provenance` | Supported | Shows source turn/session context and payload hash. |
| `mem_health` | Supported | Project health diagnostics without mutating memory. |
| `mem_health_runtime` | Supported | PID, uptime, request counts, idle timeout, and lifecycle state. |
| Snapshot list/create/restore | Supported | Restores derived state, not silent history mutation. |
| Policies / inheritance / repairs | Supported | Governed local memory control. |
| Context sync metrics | Supported | Pack sync/skip events exposed through API/UI. |
| Optional HTTP notify wrapper | Supported | Secondary local path. |

## Deferred or external surfaces

| Surface | Status | Notes |
| --- | --- | --- |
| Hosted web bridges | Outside public core | Not part of the `1.0.x` local-first package. |
| ChatGPT web / Claude web hosted flows | Outside public core | Do not treat lab bridge experiments as public core support. |
| Vector search / embeddings | Deferred | Not required for v1.0.x local continuity. |
| Remote telemetry | Not included | No remote telemetry is required for the public core. |

## Version support

| Component | Current expectation |
| --- | --- |
| Release line | `1.0.x` |
| Python | 3.12+ |
| SQLite | Local system SQLite with FTS5 support preferred |
| Integration model | MCP config plus local ingestion path |
