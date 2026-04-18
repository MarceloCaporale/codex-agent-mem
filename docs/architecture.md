# Architecture

codex-agent-mem stays intentionally narrow in the current release line:

1. Codex emits `agent-turn-complete`
2. `codex-agent-mem-codex-notify` normalizes the payload
3. the event is persisted into local SQLite
4. heuristics extract a `session_summary` and zero or more `decision` observations
5. a compact working-memory pack is compiled from recent turns and durable decisions
6. if that pack is smaller than the source context, the current directory `AGENTS.md` is updated
7. Codex or another client reads those observations and compact packs through MCP
8. the local FastAPI inspector renders projects, sessions, turns, observations, and the generated pack from the same store

## Design choices

- Local-first SQLite with FTS5
- Progressive disclosure retrieval
- AGENTS-based continuity reinjection only when compression is favorable
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
