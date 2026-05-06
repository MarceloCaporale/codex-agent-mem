# Discoverability Metadata

This document captures the metadata and phrasing that best describes the current repository for GitHub, search, and agent-driven discovery.

## Recommended GitHub description

`Persistent local MCP memory for AI agents: scoped continuity packs, writable notes, closure checks, and token-aware context reuse for Codex, Claude Code, Gemini CLI, Qwen Code, and other MCP-compatible clients.`

## Recommended GitHub topics

- `codex`
- `claude-code`
- `gemini-cli`
- `mcp`
- `model-context-protocol`
- `sqlite`
- `agent-memory`
- `mcp-memory`
- `ai-agents`
- `ai-agent-memory`
- `local-first`
- `token-efficiency`
- `context-compression`
- `agent-workflows`
- `deepseek`
- `ollama`
- `kimi`
- `fastapi`
- `developer-tools`
- `python`

## Recommended release framing

`1.0.1` is the current public maintenance release for the stable `1.0.x`
local-first MCP core.
The `1.0.x` line is a stable local-first MCP continuity layer for
MCP-compatible AI agents built on SQLite, scoped continuity packs, deterministic closure
control, recent-change deltas, scope-guard retrieval, operational-state
carry-forward, provenance-aware auditing, health diagnostics, project
snapshots, read-only runtime mode, compact MCP responses, pack-hash reuse,
lazy SQLite initialization, runtime heartbeat diagnostics, optional telemetry,
an optional local daemon/stdio bridge, MCP retrieval, and a local inspection
UI.

`v1.0.1` also hardens daemon/stdio transport behavior, documents client
response-mode differences, keeps object-root MCP `structuredContent` for list
results, and adds release hygiene gates. `1.0.0` remains the reproducible
verification baseline for the original token-reduction fixtures.

`codex-agent-mem` can also be documented as an optional companion to
`clean-process-ended` ([GitHub](https://github.com/MarceloCaporale/clean-process-ended))
v0.7.2. The projects are independent: `codex-agent-mem` preserves continuity
and closure state, while `clean-process-ended` provides dry-run
process-hygiene evidence and compact janitor receipts.

## Search phrases this repo should naturally support

- Codex memory
- Codex CLI memory
- Codex Desktop memory
- Claude Code memory
- Google Gemini CLI memory
- Claude Code MCP memory
- Google Gemini CLI MCP memory
- Qwen Code MCP memory
- local MCP memory for MCP-compatible AI agents
- MCP memory
- MCP memory layer
- MCP context pack
- structuredContent MCP memory
- local SQLite MCP memory
- multi-runtime MCP memory
- local-first MCP continuity
- agent continuity memory
- local-first agent memory
- SQLite memory for Codex
- Codex notify capture
- Codex MCP retrieval
- auditable agent memory
- memory provenance for Codex
- Codex memory health
- Codex memory snapshots
- governed memory for Codex
- policy-based agent memory
- selective memory inheritance
- repairable agent memory
- context compression for agents
- token-saving context reuse for MCP-compatible AI agents
- token efficiency for AI agents
- token economy for agent workflows
- local memory layer for agent workflows
- persistent local memory for MCP clients
- MCP memory for Codex
- Claude Code memory MCP
- Gemini CLI memory MCP
- DeepSeek model workflow through MCP memory
- Qwen Code MCP memory
- Ollama model workflow with MCP memory
- Kimi Code MCP memory
- codex-agent-mem clean-process-ended
- continuity plus process hygiene for AI agents

## Rules for future docs

- Prefer explicit, real keywords over abstract marketing language
- Repeat important terms naturally:
  - `MCP`
  - `SQLite`
  - `local-first`
  - `agent memory`
  - `continuity packs`
  - `token efficiency`
  - `token-saving context reuse`
  - validated MCP clients such as `Codex`, `Claude Code`, and `Google Gemini CLI`
- Do not document deferred areas as implemented
- Keep the first section of public docs specific and concrete
- When using model-route keywords such as DeepSeek or Ollama, state the
  validated MCP client path and do not imply a native Ollama or DeepSeek MCP
  adapter in v1.0.x.
