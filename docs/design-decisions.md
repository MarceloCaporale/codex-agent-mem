# Design Decisions

This document captures the decisions that define the public `1.0.x` release
line.

## 1. Local-first before hosted complexity

The durable store is local SQLite. This keeps memory inspectable, portable, and
easy to reason about across MCP-compatible AI agents and coding workflows.

## 2. MCP retrieval is the portable surface

Runtime adapters are intentionally thin. Codex `notify` is one capture adapter;
MCP retrieval is the surface shared by Codex, Claude Code, Google Gemini CLI,
Qwen Code/Ollama workflows, and other local MCP clients.

## 3. Profile-based tool surface

The server is not a single broad menu for every client. Tool exposure is
controlled by profile:

- `minimal` for low-impact continuity checks;
- `standard` for normal read-oriented retrieval and diagnostics;
- `full` for the complete local surface.

`--read-only` remains the safety boundary for agent workflows that should not
write snapshots, policies, inheritance, repairs, or closure records.

## 4. Structured payloads first

`structuredContent` is the canonical MCP result. `content.text` is only the
client-facing text view, controlled by `--response-mode`. List results use an
object root shaped as `{items, count}` for stricter MCP clients.

## 5. Deterministic persistence before semantic enrichment

The project stores turns and extracted observations first. More advanced
semantic enrichment can come later, but the baseline must remain deterministic,
auditable, and reproducible with local tests.

## 6. Continuity includes closure control

Useful memory is not only a summary of past decisions. The continuity pack also
tracks objectives, open work, blockers, DoD gaps, recent changes, and scope
guardrails so agents do not falsely declare completion.

## 7. Token savings are measured, not promised universally

`pack_hash`, `known_pack_hash`, compact packs, and response modes reduce repeated
operational context when there is repeated context to reuse. Public percentage
claims must stay tied to reproducible fixtures or documented live evidence.

## 8. Honest scope over platform theater

The public core does not claim hosted bridges, OAuth, ChatGPT web, Claude web,
embeddings, vector retrieval, or built-in database encryption. Those areas stay
outside the `1.0.x` core unless a future release explicitly changes scope.
