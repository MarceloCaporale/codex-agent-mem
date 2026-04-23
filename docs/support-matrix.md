# Support Matrix

## Runtime and platform support

| Area | Status | Notes |
| --- | --- | --- |
| Windows local development | Supported | Primary practical target today |
| Linux CI | Supported | Covered in GitHub Actions |
| Windows CI | Supported | Covered in GitHub Actions |
| macOS local development | Expected but not verified | No CI coverage yet |
| Codex notify capture | Supported | Current primary capture path |
| AGENTS-based continuity reinjection | Supported | Opt-in through `--sync-project-doc` when the generated pack is smaller than source context |
| Operational-state carry-forward | Supported | Objective, pending work, blockers, and guardrails are derived and injected into the working-memory pack |
| False-completion guardrails | Supported | The generated pack explicitly tells Codex not to declare completion while pending work remains |
| MCP stdio retrieval | Supported | Current primary retrieval path; one process per host connection is normal |
| Codex CLI / `codex exec` via MCP stdio | Validated | Short-lived Codex CLI execution uses the same local MCP server and config style as Desktop; validated separately from the long-lived Desktop host lifecycle |
| Codex Desktop via MCP stdio | Validated | Public v1.0 verification uses Codex Desktop with GPT-5.4 in a Codex environment; this is not a ChatGPT web/app connector validation |
| Gemini CLI via MCP stdio | Validated | Live validation passed with `standard`, `read-only`, and `compact`; `mem_search` returned object-root `{items, count}` |
| Claude Code via MCP stdio | Validated | Live validation passed with Opus 4.7. For lower-overhead workflows, avoid running multiple memory MCP layers at the same time |
| Claude Code with `claude-mem` also enabled | Compatible, higher overhead observed | Coexistence works, but local validation showed larger tool surface, session-start memory injection, and stop-hook latency from the additional memory layer |
| ChatGPT web/app connector | Not validated in v1.0 | Do not infer ChatGPT connector support from the Codex Desktop + GPT-5.4 validation. ChatGPT web/app needs separate connector/bridge validation before being claimed |
| Claude web / claude.ai | Not validated in v1.0 | Do not infer Claude web support from Claude Code validation. Claude Code runs local MCP stdio servers; Claude web / claude.ai needs a separate bridge or native connector path |
| Qwen Code via MCP stdio | Validated | Live local validation passed with Qwen Code 0.15.0, Ollama, `qwen3.6:latest`, `standard`, `read-only`, and `compact`; validated `not_modified` and clean stdio exits |
| Qwen local models through Ollama | Validated smoke | `qwen3.6:35b-a3b-q8_0` and `qwen3.5:9b` both invoked `mem_health_runtime` through Qwen Code + MCP stdio; `deepseek-r1:latest` did not pass this path because Ollama reports no tool support for that model |
| DeepSeek-V3.2 through Ollama Cloud | Validated cloud-backed | `deepseek-v3.2:cloud` invoked `mem_context_pack`, `mem_search`, and `mem_health_runtime` through Qwen Code + MCP stdio; validated `not_modified`, but this is not local inference |
| Minimax M2.5 through Ollama Cloud | Validated cloud-backed | `minimax-m2.5:cloud` invoked `mem_context_pack`, `mem_search`, and `mem_health_runtime` through Qwen Code + MCP stdio; validated `not_modified`, but this is not local inference |
| Kimi Code CLI via MCP stdio | MCP-connected | Kimi Code CLI 1.38.0 connects to `codex-agent-mem` through stdio and lists 17 tools with `standard`, `read-only`, and `compact`; full Kimi K2.5 / Kimi K2.6 model tool-call validation is not claimed yet |
| GLM-5, Kimi K2.5, and Kimi K2.6 through Ollama Cloud | Continuous evaluation | `glm-5:cloud`, `kimi-k2.5:cloud`, and `kimi-k2.6:cloud` are tracked as tool-capable Ollama Cloud candidates for future live measurements |
| Ollama models with tool support | Candidate pattern | Tool-capable Ollama models can use the same MCP pattern through an MCP-capable runtime such as Qwen Code; the table records pairs already measured live |
| Grok / xAI | Externally audited | Protocol-compatible through an MCP stdio-capable orchestrator or thin JSON-RPC stdio wrapper; no local Grok CLI validation on this machine |
| Codex Desktop long-lived host note | Documented | `codex-agent-mem` hardens its own stdio runtime, but long-lived Desktop lifecycle issues can still amplify process accumulation; see the dedicated Codex Desktop note |
| `mem_context_pack` compact retrieval | Supported | Returns the compressed continuity pack and approximate token budget |
| `mem_context_pack` auto budget | Supported | Selects the smallest fitting budget profile from `micro`, `normal`, and `full` |
| `mem_recent_changes` delta retrieval | Supported | Summarizes what changed since the last meaningful continuity baseline |
| `mem_scope_guard` continuity guard | Supported | Exposes must-not-drop scope, active constraints, and closure conflicts |
| `mem_provenance` audit retrieval | Supported | Shows where one derived observation came from, including turn/session context and source payload hash |
| `mem_health` diagnostics | Supported | Reports project health score, sync quality, and structural warnings without mutating memory |
| `mem_health_runtime` diagnostics | Supported | Reports PID, uptime, request counts, idle timeout, and basic process lifecycle state for the active stdio server |
| Snapshot list/create/restore | Supported | Creates versioned project snapshots and restores them as derived state, not silent history mutation |
| FastAPI inspection API | Supported | Local inspection surface |
| Context sync metrics | Supported | Pack sync/skip events are stored per project and exposed through API/UI, including budget reason and build timing |
| Optional HTTP notify wrapper | Supported | Secondary path only |
| Codex hooks adapter | Not yet supported | Deferred |
| Codex App Server ingestion | Not yet supported | Deferred |
| Ollama adapter | Not yet supported | Deferred |
| Vector search / embeddings | Not yet supported | Deferred |
| Local inspection UI | Supported | Served by FastAPI at `/ui`, including recent changes, scope guard, closure, sync metrics, provenance, health, and snapshots |

## Version support

| Component | Current expectation |
| --- | --- |
| Python | 3.12+ |
| SQLite | Local system SQLite with FTS5 support preferred |
| Codex integration model | `notify` + MCP config |
