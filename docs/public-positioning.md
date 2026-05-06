# Public Positioning

Use this page to keep public wording consistent and evidence-based.

## Recommended short description

`codex-agent-mem` is a portable, auditable, local-first MCP memory and
continuity layer for MCP-compatible AI agents. It stores project memory locally, builds
compact continuity packs, and exposes deterministic checks for open work,
scope, provenance, and closure state.

Short marketing line:

`one local memory layer for agent workflows`

## What the project is

- Local-first MCP memory for MCP-compatible AI agents and coding workflows.
- A continuity layer that helps agents resume without replaying the same
  project context every time.
- A token-efficiency layer for repeated agent workflows: compact continuity
  first, targeted expansion only when needed, and `not_modified` reuse when a
  pack has not changed.
- A pull-based retrieval surface through MCP tools.
- An auditable local SQLite store with provenance, health, snapshots, policies,
  inheritance links, and repair proposals.
- A project that began with Codex/GPT workflows and now targets
  MCP-compatible local agent runtimes more broadly.

## What the project is not

- Not a hosted memory service.
- Not universal memory across every tool and UI.
- Not a replacement for RAG, vector search, or a semantic knowledge base.
- Not a zero-knowledge or encrypted-at-rest product in the public v1.0.x line.
- Not a secrets vault.
- Not a guarantee of fixed token savings for every prompt.
- Not magic compression or a universal reduction claim; public percentages are
  reproducible fixture results.
- Not a claim that every MCP client exposes `structuredContent` identically.

## Claims that are safe when linked to evidence

- Local-first storage and processing.
- MCP stdio retrieval, plus an optional loopback daemon/stdio bridge.
- Compact continuity packs with approximate token-budget stats.
- `pack_hash`, `known_pack_hash`, and `not_modified` support for unchanged
  packs.
- Read-only MCP mode that blocks mutating tools.
- Object-root `structuredContent`, including `{items, count}` for list results.
- Reproducible synthetic v1.0.x token-savings fixtures.
- Token efficiency / token economy wording when tied to the mechanism:
  compact continuity packs, targeted expansion, and `known_pack_hash` reuse.
- Named client validation only at the evidence level actually recorded.
- Optional pairing with `clean-process-ended`
  ([GitHub](https://github.com/MarceloCaporale/clean-process-ended)) v0.7.2
  as a companion workflow: `codex-agent-mem` preserves continuity while
  `clean-process-ended` provides dry-run local process-hygiene evidence.

## Claims to avoid

- "Universal memory".
- "Works identically in every MCP client".
- "Guaranteed token savings".
- "Guaranteed token economy".
- "Zero-knowledge", "encrypted", or "secure vault" unless a future release
  implements and validates those properties.
- "Replaces RAG".
- Hosted bridge, OAuth, or web-client support as part of the public local-first
  core unless separately validated and documented.
- Hard dependency on `clean-process-ended`
  ([GitHub](https://github.com/MarceloCaporale/clean-process-ended)); the
  pairing is optional and both MCPs work independently.

## Security wording

Use plain language:

`codex-agent-mem` stores memory in a local SQLite database. In v1.0.x that
database is plaintext by default, so users should treat it as sensitive project
data and avoid storing credentials or secrets in memory.

The optional daemon is loopback-only in the public v1.0.x line. Its bearer token
is a local safeguard for `/mcp`, not hosted authentication, TLS, OAuth, or a
remote access-control system.

Generated continuity packs are advisory project context. Current system,
developer, and user instructions remain higher priority.
