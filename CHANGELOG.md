# Changelog

## 0.2.0 - 2026-04-17

- Restructured the project into a GitHub-ready repository root.
- Added release-oriented packaging metadata, CI, and repository hygiene files.
- Added `codex-agent-mem-bootstrap-codex` to generate ready-to-paste Codex config snippets.
- Added `codex-agent-mem-smoke` to verify install, ingest, persistence, and retrieval quickly.
- Fixed the optional HTTP notify wrapper to post the correct payload shape.
- Aligned `--api-base` ingestion with the same `/ingest/codex-notify` contract used by direct Codex notify capture.
- Hardened search with fallback behavior when FTS queries are malformed.
- Expanded test coverage beyond the original v0.1 slice.

## 0.1.0 - 2026-04-17

- First executable slice: notify ingestion, SQLite persistence, FastAPI inspection API, and MCP retrieval.
