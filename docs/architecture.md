# Architecture

codex-agent-mem stays intentionally narrow in the current release line:

1. Codex emits `agent-turn-complete`
2. `codex-agent-mem-codex-notify` normalizes the payload
3. the event is persisted into local SQLite
4. heuristics extract a `session_summary`, zero or more `decision` observations, and operational-state observations
5. the store derives objective, constraints, pending work, completed work, blockers, and completion claims from those observations
6. a compact working-memory pack is compiled from recent turns, durable decisions, and operational state
7. the generated pack carries a scope guard when open work remains
8. if that pack is smaller than the source context, the current directory `AGENTS.md` is updated
9. every sync or skip is recorded into context-sync metrics
10. Codex or another client reads those observations and compact packs through MCP
11. the local FastAPI inspector renders projects, sessions, turns, observations, operational state, and sync metrics from the same store

## Design choices

- Local-first SQLite with FTS5
- Progressive disclosure retrieval
- AGENTS-based continuity reinjection only when compression is favorable
- Scope preservation beats “decision memory” alone
- False-completion guardrails are part of continuity, not optional UI sugar
- Deterministic persistence before any future semantic enrichment
- Runtime adapters kept thin
- No vendor dependency for correctness

## Current retrieval surface

- `mem_search`
- `mem_get`
- `mem_recent`
- `mem_project_brief`
- `mem_context_pack`

## Deferred areas

- embeddings
- vector search
- App Server capture
- hooks capture
- Ollama adapter
- multi-agent federation
