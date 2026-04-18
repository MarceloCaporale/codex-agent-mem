# Changelog

## 0.5.0 - 2026-04-18

- Added derived operational state for objective, constraints, pending work, completed work, blockers, and completion claims.
- Added scope guard rules to the generated continuity block so Codex carries forward open work and avoids false completion.
- Added context sync metrics and persistence for generated pack events.
- Expanded the inspector and API to surface operational state and context sync metrics.
- Hardened heuristic extraction so semicolon-separated operational clauses are split instead of contaminating one field with another.

## 0.4.1 - 2026-04-18

- Fixed the Windows MCP stdio transport by emitting ASCII-safe JSON on the wire and reconfiguring stdio to UTF-8.
- Stabilized `mem_context_pack` and the other MCP retrieval tools when called from Codex CLI on Windows.

## 0.4.0 - 2026-04-17

- Added generated working-memory context packs built from durable decisions and recent session summaries.
- Added automatic AGENTS.md synchronization after Codex notify ingest so future sessions start with compressed continuity context.
- Added `mem_context_pack` to the MCP surface and `codex-agent-mem-refresh-context` for manual context regeneration.
- Added project UI support to inspect the generated working-memory pack and its approximate token budget.

## 0.3.0 - 2026-04-17

- Added a local inspection UI served by FastAPI for projects, sessions, turns, observations, and decisions.
- Added packaged HTML templates and CSS so the inspector works from installed wheels, not just from source checkouts.
- Expanded the store and tests to cover inspector views and turn-level browsing.

## 0.2.1 - 2026-04-17

- Updated the generated Codex config snippet to auto-approve the read-only MCP retrieval tools.
- Updated the Codex config example and integration docs to match the real non-interactive Codex behavior.

## 0.2.0 - 2026-04-17

- Restructured the project into a GitHub-ready repository root.
- Added release-oriented packaging metadata, CI, and repository hygiene files.
- Added `codex-agent-mem-bootstrap-codex` to generate ready-to-paste Codex config snippets.
- Added `codex-agent-mem-smoke` to verify install, ingest, persistence, and retrieval quickly.
- Fixed the optional HTTP notify wrapper to post the correct payload shape.
- Aligned `--api-base` ingestion with the same `/ingest/codex-notify` contract used by direct Codex notify capture.
- Hardened search with fallback behavior when FTS queries are malformed.
- Expanded test coverage beyond the original v0.1 slice.
- Added agent-facing and public-facing repository docs: `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, quickstart, integration, support matrix, design decisions, and discoverability metadata.
- Updated package metadata to reflect Apache 2.0 licensing and stronger public discoverability keywords.

## 0.1.0 - 2026-04-17

- First executable slice: notify ingestion, SQLite persistence, FastAPI inspection API, and MCP retrieval.
