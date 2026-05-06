# Architecture

`codex-agent-mem` is a local-first MCP memory layer. Codex was the first
adapter, but the public core is designed around portable MCP retrieval and
local SQLite persistence.

## Core flow

1. A local capture adapter or API submits an agent turn.
2. The payload is normalized into a generic event envelope.
3. The event is persisted into local SQLite with FTS-backed retrieval.
4. Heuristics extract operational observations:
   - session summaries;
   - user requests;
   - objectives;
   - decisions;
   - constraints;
   - pending and completed work;
   - blockers;
   - project, mission, and session Definition of Done items;
   - completion claims.
5. The store derives project operational state from those observations.
6. `mem_bootstrap_context` resolves startup scope defensively from explicit
   thread/path hints before active context is loaded.
7. `mem_context_pack` builds a scoped continuity pack from recent turns,
   durable decisions, open work, DoD state, and scope guardrails.
8. `pack_hash` and `known_pack_hash` avoid resending unchanged continuity
   packs.
9. MCP clients retrieve memory, open work, health, provenance, snapshots,
   policies, inheritance, repairs, and runtime health through the configured
   profile.
10. The optional local API/UI renders the same store for inspection.
11. Optional `AGENTS.md` sync writes a generated continuity block only when
    compression is favorable.

## Scope model

`project_key` is the broad workspace or project scope. It may intentionally
cover several chats, agents, or client runtimes.

Capture adapters resolve project identity from explicit configuration first,
then from referenced repository paths, AGENTS scope, project-state canonical
names, and finally the working directory. Technical working directories and
broad roots are treated cautiously so they do not become accidental project
keys when the turn clearly points to a narrower project.

`session_id` is the persisted chat/session scope inside that project. v1.0.1
exposes `mem_session_list(project_key)`, `mem_scope_resolve(project_key, hint)`,
and optional `session_id` filters on retrieval tools so broad project scopes
can be narrowed without changing the database model. `mem_scope_resolve` and
`mem_session_list` use explicit hints such as chat title, cwd/repo path, query,
or sub-scope hint; those hints are selection aids, not a formal sub-project
taxonomy.

The current live turn is not guaranteed to appear in retrieval until it has been
captured and persisted. Session-aware retrieval filters stored local memory; it
does not add live message tracking or hosted sync.

Project-wide packs can still be useful for broad continuity, but v1.0.1 treats
multi-session or multi-sub-scope packs as ambiguous. Defensive startup callers
should use `mem_bootstrap_context` first. When lanes are ambiguous, it returns
candidate lanes and does not fetch a project-wide context pack. If a caller
explicitly requests `mem_context_pack(project_key)` anyway, the pack emits a
visible scope warning, reports the last captured turn, and marks the objective
as a project-wide candidate rather than live current intent.

## Capture adapters

Adapters are intentionally thin. They translate a local runtime event into the
generic envelope; they do not define the memory model.

- Codex `notify` is the historical capture adapter and remains supported.
- Generic ingestion is available for local tools that can submit normalized
  events.
- MCP retrieval is the portable surface used by Codex, Claude Code, Google
  Gemini CLI, Qwen Code/Ollama workflows, and other MCP-capable local clients.

## MCP profiles

The tool surface is controlled by profile:

- `minimal`: session list, continuity pack, open work, completion check,
  runtime health.
- `standard`: read-oriented retrieval, provenance, health, snapshot listing,
  policy listing/validation, inheritance listing, and repair proposals.
- `full`: the complete local tool surface, including `mem_note_create` for
  manual operational notes; mutating tools remain blocked when `--read-only`
  is active.

This keeps low-impact clients small while preserving a complete local inspection
and governance surface for maintainers.

## Response contract

The canonical MCP payload is `structuredContent`.

- List-shaped results are wrapped as `{items, count}`.
- `mem_session_list` follows the same object-root list contract and returns
  recent persisted sessions for one `project_key`, optionally filtered by
  `query` / `sub_scope_hint` to help choose a session in broad workspaces.
- `mem_scope_resolve` and `mem_bootstrap_context` are read-only startup
  helpers. They expose candidate lanes and avoid silent broad-pack retrieval
  when a broad project key contains several possible threads.
- `content.text` is a response-mode view:
  - `compact` for short text when the client exposes structured payloads;
  - `balanced` for short text plus a pointer to `structuredContent`;
  - `verbose` when the client needs payloads rendered into text.

## Local runtime surfaces

- MCP stdio server: primary retrieval surface.
- Optional loopback daemon: local process-sharing optimization; not a remote
  service.
- FastAPI UI: local inspection surface at `/ui`.
- SQLite database: plaintext local store by default.

## Deferred areas

The public `1.0.x` core does not require embeddings, vector search, hosted web
bridges, OAuth, ChatGPT web integration, Claude web integration, or a SaaS
backend.
