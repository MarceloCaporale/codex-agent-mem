# Release Notes v1.0.1

Released: 2026-05-06

`codex-agent-mem` v1.0.1 is a public hardening release for the local-first MCP
core. It focuses on transport stability, daemon safety, MCP payload
compatibility, and clearer validation boundaries. It does not introduce a data
migration.

## Highlights

- Fixed one optional daemon/stdio bridge idle-timeout path that could present as
  a false `Transport closed` incident when `codex-agent-mem-mcp --daemon-url`
  was used.
- Kept direct stdio behavior unchanged: direct `codex-agent-mem-mcp` still uses
  the defensive idle timeout unless configured otherwise.
- Serialized request handling inside the optional threaded local daemon so one
  shared SQLite-backed server instance is not driven concurrently.
- Hardened the public local daemon surface with loopback-only bind validation,
  optional bearer-token protection for `/mcp`, sanitized `/health`, and token
  forwarding from the stdio bridge.
- Normalized MCP `structuredContent` for list-returning tools so clients receive
  object roots shaped as `{items, count}` instead of root arrays.
- Added session-aware retrieval for persisted memory. Agents can call
  `mem_session_list(project_key, limit)` and pass optional `session_id` to
  retrieval tools such as `mem_context_pack`, `mem_search`,
  `mem_recent`, `mem_project_brief`, `mem_open_work`, `mem_completion_check`,
  `mem_scope_guard`, and `mem_recent_changes` to avoid cross-session context
  bleed in broad project scopes. This filters stored local memory only; it does
  not add live current-turn awareness.
- Added defensive startup scope helpers. `mem_scope_resolve` ranks candidate
  lanes from explicit thread/path/query hints, while `mem_bootstrap_context`
  returns a scoped pack only when `session_id` is explicit. If a broad project
  key contains several plausible lanes, it returns candidate lanes and
  narrowing instructions instead of silently treating a project-wide pack as the
  active thread or auto-selecting a session.
- Added `mem_note_create` for explicit manual operational memory writes.
  Manual notes are stored as indexed observations, can be scoped to a validated
  `session_id`, are searchable through `mem_search`, and are eligible for
  `mem_context_pack`. Snapshots remain versioned state captures and are not the
  manual note mechanism.
- Clarified the mutability contract: normal continuity installations are
  writable by default so agents can persist snapshots and closure/governance
  writes when those tools are enabled. `--read-only` is an explicit
  retrieval-only audit/debug mode.
- Updated the public Codex config example to use writable `full` mode by
  default and moved `--read-only` into a separate retrieval-only audit/debug
  example.
- Aligned Codex bootstrap tool approvals with MCP profile definitions and
  split validation evidence between retrieval-only (`L3-R`) and writable
  continuity (`L3-W`) claims.
- Extended the release smoke so a manual note written by one writable MCP
  subprocess must remain retrievable through `mem_search` and
  `mem_context_pack` from a later MCP subprocess over the same temporary
  SQLite database.
- Documented that `mem_note_create` requires an existing `project_key`, and
  that the `full` Codex example approves writable note, snapshot, governance,
  repair, and restore tools.
- Hardened snapshot provenance for broad project scopes. `mem_snapshot_create`
  now accepts optional `session_id`, validates that it belongs to
  `project_key`, records high-confidence session provenance only when the
  session is explicit, and otherwise leaves the snapshot unassociated instead
  of silently attaching it to the latest project turn. `mem_snapshot_list`
  exposes snapshot/session provenance fields for auditability.
- Hardened notify/API project identity resolution so broad workspace or
  technical working directories do not become accidental `project_key` values
  when the captured turn clearly references a narrower repository, AGENTS
  scope, or project-state canonical name.
- Hardened broad project-scope retrieval: project-wide packs now warn when they
  span multiple persisted sessions or inferred sub-scopes, mark the objective as
  a project-wide candidate, collapse repeated retrieval items, cap per-session
  dominance in global packs, improve session labels, and expose capture
  freshness/provenance.
- Kept retrieval hygiene conservative: `pack_hash` ignores volatile age fields,
  dedupe preserves distinct operational type/status states, and session-level
  version metadata is reported as session-scoped provenance rather than exact
  per-observation capture certainty.
- Preserved response-diet behavior after retrieval hardening: repeated
  unchanged packs still short-circuit through `known_pack_hash` /
  `not_modified`, compact text keeps only routing breadcrumbs, and detailed
  scope/provenance remains in `structuredContent`.
- Kept compact `content.text` as the default while retaining full payloads in
  `structuredContent`; clients that hide structured payloads can use
  `--response-mode verbose`.
- Added generated-context wording that marks retrieved memory as advisory
  project context, below system, developer, and user instructions.
- Clarified that v1.0.x local SQLite storage is plaintext by default and should
  not be used as a secrets vault.
- Documented the optional companion workflow with `clean-process-ended`
  ([GitHub](https://github.com/MarceloCaporale/clean-process-ended)) v0.7.2:
  `codex-agent-mem` preserves continuity and closure state, while
  `clean-process-ended` provides dry-run local process-hygiene evidence. The
  tools remain independent and neither is a hard dependency of the other.

## Client guidance

- Codex Desktop and Codex CLI can use compact mode when the agent can access the
  useful structured payload.
- Claude Code benefits from object-root `structuredContent` for list results.
- Google Gemini CLI should be checked after configuration: if compact mode only
  exposes a one-line summary to the agent, use `--response-mode verbose`.
- Google Antigravity should follow the same MCP response-mode guidance when
  configured through the same MCP bridge surface, but independent live
  Antigravity validation is not claimed by this release note.

## Token efficiency and continuity

The existing public v1.0.x synthetic fixtures continue to show that compact
continuity packs can avoid resending repeated operational context. The fixture
range is 86.26% to 97.24% reduction for those controlled repeated-context
scenarios, with `not_modified=true` on repeated unchanged packs.

This is token efficiency for agent workflows, not magic compression. These
numbers are not universal guarantees. Sustained-use evaluations should measure
source context tokens, pack tokens, `not_modified` frequency, targeted
expansion calls, and continuity quality across multiple sessions.

See [Token-Savings Methodology](./docs/benchmarks/token-savings.md).

## Validation and support

Public validation is documented by evidence level:

- [Validation](./docs/validation/VALIDATION.md)
- [Runtime Support](./docs/validation/runtime-support.md)
- [Client Behavior](./docs/validation/client-behavior.md)
- [Verification Evidence](./docs/verification/README.md)

## Security boundary

v1.0.1 remains local-first. The optional daemon is a loopback local component,
not a hosted service. The bearer token is a local safeguard, not OAuth, TLS, or
remote access control. SQLite memory is plaintext by default in v1.0.x.

## Upgrade notes

- No data migration is required.
- Restart MCP clients after upgrade so they refresh the tool schema and see
  `mem_session_list`, `mem_note_create`, and the optional `session_id`
  parameters.
- Review MCP client configuration if a client cannot see useful
  `structuredContent` in compact mode.
- Use `--read-only` only for retrieval-only audit/debug workflows.
- Use temporary databases for smoke tests and release validation.
