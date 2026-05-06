# Changelog

## 1.0.1 - Prepared 2026-05-06

- Stabilized the public local-first MCP runtime for multi-client use while keeping the core package local, auditable, and SQLite-backed.
- Normalized MCP `structuredContent` so list-returning tools expose object roots as `{items, count}` instead of root arrays. This is a wire-format compatibility fix for stricter MCP clients, not a data migration.
- Added session-aware retrieval for persisted memory: agents can list recent sessions with `mem_session_list` and pass optional `session_id` to retrieval tools to avoid cross-session context bleed in broad project scopes. This is retrieval over stored local memory, not live current-turn awareness.
- Added defensive startup scope resolution for broad workspaces: `mem_scope_resolve` exposes candidate lanes from explicit hints, and `mem_bootstrap_context` returns a session-scoped pack only when `session_id` is explicit; otherwise it returns narrowing guidance instead of silently loading a project-wide pack or auto-selecting a session.
- Added `mem_note_create` as the explicit writable path for manual operational memory. Notes are persisted as indexed observations, can be scoped to a validated `session_id`, are blocked by `--read-only`, appear in `mem_search`, and are eligible for `mem_context_pack`; snapshots remain versioned state captures, not the manual note mechanism.
- Hardened `mem_snapshot_create` / `mem_snapshot_list` provenance for broad project scopes: snapshots can be tied to an explicit internal `session_id`, invalid cross-project session IDs are rejected, and unscoped snapshots are no longer silently associated with the latest project turn.
- Recalibrated public quickstart, Codex config examples, runtime guidance, and the MCP contract smoke so normal continuity installations are writable by default; `--read-only` remains an explicit retrieval-only audit/debug mode.
- Aligned Codex bootstrap tool approvals with the MCP profile definitions and added anti-drift coverage so `minimal`, `standard`, and `full` approval surfaces stay matched to `tools/list`.
- Split public validation claims into retrieval-only and writable-continuity evidence so read-only client smokes are no longer presented as full continuity validation.
- Extended the MCP contract smoke to verify later-process continuity: a manual note written through one writable MCP subprocess must be found by `mem_search`, included in `mem_context_pack`, and return `not_modified=true` from a later subprocess over the same temporary SQLite database.
- Documented that `mem_note_create` requires an existing `project_key`, and that the `full` Codex example approves writable note, snapshot, governance, repair, and restore tools.
- Hardened Codex notify/API project identity resolution so broad workspace roots and technical working directories are not persisted as accidental project keys when the captured turn identifies a narrower repository, AGENTS scope, or project-state canonical name.
- Hardened broad project-scope retrieval with visible multi-session scope warnings, project-wide candidate objective labeling, retrieval dedupe, per-session dominance caps, clearer session labels, search provenance, and persisted-memory freshness cues.
- Kept the hardening conservative by excluding volatile age from stable pack hashes, deduping by type/status/text so operational states remain distinct, overfetching before search dedupe, preserving protected operational items under dominance caps, and reporting session-level version metadata without claiming per-observation capture certainty.
- Added response-diet no-regression coverage for post-hardening retrieval: compact text keeps only scope breadcrumbs, unchanged packs still return `not_modified=true`, and public token-savings claims remain tied to reproducible fixtures rather than universal guarantees.
- Kept compact `content.text` as the default response diet for clients that consume `structuredContent`, and documented when Google Gemini CLI / Google Antigravity should use `response_mode=verbose` to expose useful payload text to the model.
- Changed the stdio bridge default so `codex-agent-mem-mcp --daemon-url ...` no longer exits after the defensive 300 second idle timeout unless `--idle-timeout-seconds` is explicitly provided.
- Kept direct stdio behavior unchanged: direct `codex-agent-mem-mcp` still defaults to a 300 second defensive idle shutdown, and `--idle-timeout-seconds 0` still disables it.
- Serialized MCP request handling inside the optional threaded local daemon so one shared SQLite-backed server instance is not driven concurrently.
- Hardened the optional local daemon for the public local-first line: loopback-only bind validation, optional bearer token auth for `/mcp`, sanitized public `/health`, and bearer-token forwarding from the stdio bridge.
- Added a generated-context guardrail that marks retrieved memory as advisory project context rather than higher-priority instruction, plus public documentation that `1.0.x` local SQLite storage is plaintext by default and must not be used as a secrets vault.
- Added release validation coverage for bridge idle-timeout resolution, local daemon request handling, `known_pack_hash` / `not_modified`, and object-root list payloads.
- This release keeps hosted/web/OAuth bridge work outside the public core and keeps token-savings claims tied to reproducible methodology rather than universal guarantees.

## 1.0.0 - 2026-04-21

- Added low-impact MCP runtime modes with `--profile minimal|standard|full`, `--read-only`, and enriched `mem_health_runtime` fields for profile, mutability, cache, lazy initialization, and spawn-storm diagnostics.
- Added response diet support: compact `content.text` by default, full data retained in `structuredContent`, and `--response-mode compact|balanced|verbose` for debugging or compatibility needs.
- Added lazy store initialization so `initialize`, `tools/list`, and `mem_health_runtime` can run without opening SQLite.
- Added short in-process caching for expensive read tools using project revision fingerprints instead of SQLite file mtimes.
- Added stable `pack_hash` support for `mem_context_pack`, plus `known_pack_hash` / `not_modified` responses to avoid resending unchanged continuity packs.
- Added local heartbeat-based runtime diagnostics, `same_db_process_count`, and `spawn_storm_warning` without adding a process-inspection dependency.
- Added optional local runtime telemetry with bounded `events.jsonl` output and `off|summary|debug` modes.
- Added an optional local MCP daemon and stdio bridge through `codex-agent-mem-daemon` and `codex-agent-mem-mcp --daemon-url ...`; stdio remains the default.
- Added reproducible public verification evidence under `docs/verification/`, including token-savings metrics, lazy-init checks, read-only safety, response diet, telemetry smoke, and a sub-agent handoff scenario.

## 0.9.0 - 2026-04-18

- Added governed memory policies for inclusion and exclusion control through `mem_policy_validate`, `mem_policy_add`, `mem_policy_list`, and `mem_policy_remove`.
- Added selective inheritance links so one project can carry forward approved continuity from another project without blindly importing everything.
- Added governed repair proposals and derived repair events through `mem_repair_propose` and `mem_repair_apply`.
- Extended the context-pack builder so target policies also apply to inherited memory, preventing excluded items from leaking into generated packs.
- Added a local policy CLI and inspector/UI support for governance state, including policies, inheritance links, repairs, and their compact summaries.
- Hardened the MCP stdio runtime with configurable idle shutdown, signal-aware cleanup, explicit SQLite close, and lifecycle logging for process diagnostics.
- Added `mem_health_runtime`, plus SQLite `WAL` / `busy_timeout` defaults better suited to multiple MCP and notify processes touching the same local database.
- Switched bootstrap examples so `--sync-project-doc` is opt-in instead of on by default, while keeping automatic reinjection available when explicitly enabled.

## 0.8.0 - 2026-04-18

- Added auditable memory provenance persisted per observation and exposed through `mem_provenance`.
- Added diagnostic health reporting through `mem_health`, plus persisted health reports per project.
- Added snapshot creation, listing, and restore flows through `mem_snapshot_create`, `mem_snapshot_list`, `mem_snapshot_restore`, and a local snapshot CLI.
- Added provenance, health, and snapshot visibility to the FastAPI inspector and local UI.
- Hardened diagnostic-turn filtering so `mem_*` verification runs do not pollute derived operational state or `AGENTS.md`.
- Persisted richer context-sync observability, including budget reasons and sync build timing.

## 0.7.0 - 2026-04-18

- Added `mem_recent_changes` to expose open-work deltas since the last meaningful sync baseline.
- Added `mem_scope_guard` to surface must-not-drop continuity, active constraints, and closure conflicts.
- Added `budget=auto` for context packs, selecting the smallest fitting reinjection profile from `micro`, `normal`, and `full`.
- Persisted context-sync metrics by budget, including event counts and average compression ratio per budget.
- Filtered diagnostic MCP and no-tools verification turns out of derived operational state so inspection runs do not pollute continuity.
- Expanded the local inspection UI to surface recent changes and scope guard state alongside closure and sync metrics.

## 0.6.0 - 2026-04-18

- Added hierarchical Definition of Done tracking across project, mission, and session scopes.
- Added deterministic closure control with `mem_open_work` and `mem_completion_check`.
- Added `closure_mismatch` metrics and persisted closure-check event summaries per project.
- Added budgeted context packs (`micro`, `normal`, `full`) with compact reinjection stats.
- Hardened inline extraction and semantic deduplication so DoD labels and near-duplicate blockers are classified correctly.

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
