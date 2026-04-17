# Design Decisions

This document captures the decisions that define the current release line.

## 1. Local-first before hosted complexity

The durable store is local SQLite. This keeps the system inspectable, portable, and easy to reason about during the early public phase.

## 2. Narrow MCP surface

The MCP server intentionally exposes a small retrieval surface:

- `mem_search`
- `mem_get`
- `mem_recent`
- `mem_project_brief`

The goal is reliable retrieval, not a broad unfinished tool menu.

## 3. Deterministic persistence before semantic enrichment

The project stores turns and extracted observations first. More advanced semantic enrichment can come later, but the baseline must remain deterministic and auditable.

## 4. Thin runtime adapters

Codex integration is intentionally thin:

- `notify` captures turns
- MCP exposes retrieval

This keeps the runtime contract explicit and reduces hidden coupling.

## 5. Honest scope over platform theater

The repository does not present hooks capture, App Server ingestion, embeddings, vector retrieval, or UI as implemented. Deferred work stays documented as deferred.
