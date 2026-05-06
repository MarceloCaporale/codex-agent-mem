# Runtime Support

This matrix describes the public v1.0.x support posture. It separates local
runtime support from client-specific evidence so users can see what was tested,
what is documented by contract, and what remains only expected compatibility.

## Platform and runtime support

| Area | Status | Evidence level | Notes |
| --- | --- | --- | --- |
| Python 3.12+ | Supported | L1 | Declared in `pyproject.toml`; tests run against the package code. |
| Windows local development | Supported | L2/L3-R/L3-W | Primary practical target for local MCP use. |
| Linux CI | Supported | L1 | Covered by the public CI posture and release checklist. |
| macOS local development | Expected, not independently verified in this release | L0 | No v1.0.x macOS-specific public validation is claimed. |
| MCP stdio server | Supported | L1/L3-R/L3-W | Default local MCP transport. One process per host connection is normal. |
| Optional local daemon | Supported for loopback use only | L1 | Rejects non-loopback bind hosts in the public core. |
| Optional daemon bearer token | Supported as a local safeguard | L1 | Protects `/mcp`; it is not TLS, OAuth, or hosted authentication. |
| Local SQLite persistence | Supported | L1 | Plaintext by default. Treat the database as sensitive project data. |
| Local API/UI | Supported | L1 | Local inspection surface, not a hosted service. |
| Hosted web bridges | Outside public v1.0.x core | L0 | Do not infer support from local MCP validation. |

## MCP profiles

| Profile | Intended use | Tool surface |
| --- | --- | --- |
| `minimal` | Low-impact continuity checks for long-lived clients. | `mem_session_list`, `mem_scope_resolve`, `mem_bootstrap_context`, `mem_context_pack`, `mem_open_work`, `mem_completion_check`, `mem_health_runtime`. |
| `standard` | Read-oriented continuity, search, provenance, health, and governance inspection. | Read-oriented retrieval, health, provenance, snapshot listing, policy listing/validation, inheritance listing, and repair proposal tools. |
| `full` | Normal continuity mode when MCP-side snapshots, governance, repair, or closure writes are expected. | All MCP tools, unless `--read-only` is explicitly enabled to block mutating calls. |

Normal continuity installations should be writable. Use `--read-only` only when
an agent should retrieve continuity and diagnostics without writing snapshots,
policies, inheritance links, repairs, or closure events.

## Response modes

| Mode | `content.text` behavior | `structuredContent` behavior |
| --- | --- | --- |
| `compact` | Short summary intended to reduce visible text overhead. | Complete structured payload remains present in the MCP result. |
| `balanced` | Short summary plus a note that the complete payload is in `structuredContent`. | Complete structured payload remains present. |
| `verbose` | JSON-formatted text version of the payload. | Complete structured payload remains present. |

Prefer `compact` when the client exposes `structuredContent` to the model or
tool layer. Use `verbose` for debugging or when the client hides the useful
structured payload from the agent.

## Session-aware retrieval

`mem_session_list(project_key)` lists recent persisted sessions/chats for a
project. `mem_scope_resolve` and `mem_bootstrap_context` are the defensive
startup path for broad workspaces: they return candidate lanes/sub-scopes and
set `do_not_fetch_project_wide_pack=true` instead of silently treating a broad
project pack as active context. `mem_session_list` also accepts `query` /
`sub_scope_hint` to help large broad workspaces find the right session.
Retrieval tools accept optional `session_id` so broad workspaces can avoid
mixing unrelated chats or agents while keeping `project_key` as the primary
scope.

This filters stored local memory only. A current live turn must be captured
before it can appear in session-aware retrieval.

## Client evidence snapshot

| Client/runtime | Recommended mode | Evidence level | Current claim |
| --- | --- | --- | --- |
| Codex Desktop | `full`, writable, `compact`; longer idle timeout for long-lived sessions. | L3-W bridge smoke plus L1/L3-R evidence | Local MCP validation, writable manual-note and snapshot-provenance smokes, and reproducible synthetic fixture evidence. |
| Codex CLI / `codex exec` | `standard` or `full`, writable, `compact`. | L3-R plus L1 fixtures | Short-lived local MCP retrieval path validated separately from long-lived Desktop behavior; writable continuity is covered by the bridge smoke unless a separate live client note says otherwise. |
| Claude Code | `standard` or `full`, writable, `compact`. | L3-W bridge smoke plus L3-R evidence | Live local retrieval validation, object-root list payloads, and writable bridge smoke evidence; use `full` when MCP-side writes are required. |
| Google Gemini CLI | `standard` or `full`, writable; use `verbose` if compact mode only exposes summaries to the agent. | L3-W bridge smoke plus L3-R evidence | Live local retrieval calls observed. Compact may be insufficient in clients that hide `structuredContent`; writable continuity is covered by the bridge smoke unless a separate live client note says otherwise. |
| Google Antigravity | Same MCP bridge guidance as Google Gemini CLI when configured through the same MCP surface. | L0 unless a live run is recorded | Documented configuration guidance only; no independent v1.0.x live Antigravity validation is claimed here. |
| Qwen Code with local Ollama models | `standard` or `full`, writable for continuity; `--read-only` only for retrieval-only checks. | L3-R | Current v1.0.1 evidence is retrieval-only live MCP validation through Qwen Code and Ollama-backed models. |
| DeepSeek-V3.2 through Ollama Cloud | `standard` or `full`, writable for continuity; `--read-only` only for retrieval-only checks. | L3-R | Current v1.0.1 evidence is retrieval-only cloud-backed MCP workflow validation through an MCP-capable local client. |
| Minimax M2.5 through Ollama Cloud | `standard` or `full`, writable for continuity; `--read-only` only for retrieval-only checks. | L3-R | Current v1.0.1 evidence is retrieval-only cloud-backed MCP workflow validation through an MCP-capable local client. |
| Kimi Code CLI | `standard` or `full`, writable for continuity; `--read-only` only for retrieval-only checks. | L2 connection validation | MCP connection and tool listing validated; full model tool-call behavior is not claimed. |
| Grok / xAI style orchestrators | Client-specific. | L4 | Protocol-level compatibility review only. |

Evidence notes for these rows are kept under [evidence](./evidence/README.md).
They are intentionally brief and public-safe; private transcripts and
operational database contents are not required for the public release claim.

## Practical guidance

- If the agent can see the full pack text from `mem_context_pack` in compact
  mode, keep compact mode.
- If the agent sees only a short line such as a context-pack summary and cannot
  use the pack itself, switch that client to `--response-mode verbose`.
- For Google Gemini CLI and Google Antigravity-style MCP use, prefer explicit
  verification after configuration: call `mem_health_runtime`, then
  `mem_bootstrap_context`. Call `mem_context_pack` directly only with explicit
  `session_id` or after the bootstrap result says the project-wide scope is not
  broad.
- Record new client claims with the validation level used in
  [Validation](./VALIDATION.md).
