# Validation

This page defines how public validation claims are stated for
`codex-agent-mem` v1.0.x. It is a validation map, not a promise that every MCP
client exposes the same UI, payload envelope, or model-visible text.

## Validation levels

| Level | Meaning | Acceptable evidence |
| --- | --- | --- |
| L0 - Documented contract | Behavior is described by source, tests, or docs, but not independently exercised for a named client in this release. | Source review, test coverage, or configuration docs. |
| L1 - Automated fixture | Behavior is exercised by reproducible local fixtures with synthetic data. | `pytest`, verification runner output, temporary database runs. |
| L2 - Local MCP runtime | A real local MCP server or daemon path was exercised outside pure unit tests. | `mem_health_runtime`, tool calls, response payload checks, temporary database smoke. |
| L3-R - Live client runtime retrieval | A named MCP client/model pair made real retrieval or diagnostic tool calls. The mutability mode must be declared. If `read_only=true`, the claim is retrieval-only and does not validate persistent writable continuity. | Client transcript, request counters, tool payload shape, mutability mode, `not_modified` behavior where visible. |
| L3-W - Live writable continuity runtime | A named MCP client/runtime demonstrated write, persist, retrieve, and reuse of operational memory or another explicitly scoped writable continuity artifact. | Tool transcript or smoke evidence showing `read_only=false`, a mutating write, later retrieval through `mem_search`, `mem_context_pack`, or an equivalent continuity path. |
| L4 - External protocol review | A third-party or external review checked protocol compatibility, but this release does not claim a live local model run. | Review artifact or compatibility note with stated limits. |

When a row says "validated", it means validated at the level named in that
row. It does not imply hosted service support, identical client behavior, or a
universal token-savings guarantee.

## Current v1.0.x evidence

| Area | Level | Evidence |
| --- | --- | --- |
| Version identity | L1 | `pyproject.toml` and `src/codex_agent_mem/__init__.py` report `1.0.2`. |
| MCP list payload shape | L1 | `structuredContent` returns object roots; list values are wrapped as `{items, count}` in `src/codex_agent_mem/mcp_stdio.py` and covered by `tests/test_mcp.py`. |
| `content.text` response diet | L1 | Compact, balanced, and verbose text modes are covered by `tests/test_mcp_v1_runtime_efficiency.py` and fixture results. |
| `pack_hash` / `known_pack_hash` / `not_modified` | L1 | `mem_context_pack` returns a stable `pack_hash`; repeated calls with `known_pack_hash` return `not_modified=true` when unchanged. |
| Session-aware retrieval | L1/L3-R | `mem_session_list` and optional `session_id` filters are covered by tests, MCP smoke, and retrieval-mode client evidence for Codex, Google Gemini CLI, and Claude Code. |
| Defensive startup scope resolution | L1 | `mem_scope_resolve` and `mem_bootstrap_context` are covered by session-aware retrieval tests and evidence; broad projects return candidate lanes and `do_not_fetch_project_wide_pack=true` instead of silently loading a global active pack. |
| Manual operational notes | L1/L3-W | `mem_note_create` is covered by tests and writable bridge evidence showing manual memory writes, `mem_search`, and `mem_context_pack` retrieval. |
| Project identity resolution | L1 | Codex notify/API fixtures cover broad workspace roots, referenced repository paths, AGENTS scope, project-state canonical names, and technical working-directory fallbacks. |
| Retrieval-hygiene response diet | L1 | Post-hardening fixtures verify compact scope warnings, stable `known_pack_hash`, search overfetch before dedupe, dominance caps with protected operational items, and freshness breadcrumbs without expanding compact text into a full payload. |
| Read-only mode | L1 | Mutating tools are blocked in read-only mode; `mem_completion_check` avoids closure writes when read-only. |
| Minimal profile lazy initialization | L1 | `initialize`, `tools/list`, and `mem_health_runtime` do not open SQLite before a DB-backed tool is used. |
| Optional daemon bridge | L1 | Tests cover loopback bind validation, optional bearer token handling, sanitized `/health`, bridge token forwarding, and serialized daemon request handling. |
| Token-savings fixtures | L1 | Synthetic v1.0.x fixtures are published under `docs/verification/v1.0.0/`. |
| Local-first security boundary | L0/L1 | Public docs and tests describe local SQLite, plaintext storage by default, loopback-only daemon hardening, and advisory generated context. |

## Public evidence files

- [Verification evidence](../verification/README.md)
- [v1.0.x verification results](../verification/v1.0.0/RESULTS.md)
- [v1.0.x verification methodology](../verification/v1.0.0/METHODOLOGY.md)
- [Client evidence index](./evidence/README.md)
- [Writable runtime evidence](./evidence/writable-runtime-v1.0.1.md)
- [Manual notes runtime evidence](./evidence/manual-notes-runtime-v1.0.1.md)
- [Session-aware retrieval evidence](./evidence/session-aware-retrieval-v1.0.1.md)
- [Runtime support](./runtime-support.md)
- [Client behavior](./client-behavior.md)
- [Token-savings methodology](../benchmarks/token-savings.md)

## Validation boundaries

- The public core is local-first MCP stdio, the optional loopback daemon/stdio
  bridge, local SQLite, and the local API/UI.
- Hosted bridges, OAuth web flows, SaaS deployment, and commercial bridge work
  are outside the public v1.0.x core unless separately documented and validated.
- SQLite is plaintext by default in v1.0.x. The project does not claim
  zero-knowledge storage, built-in encryption at rest, or secret-vault behavior.
- `structuredContent` is the canonical payload. `content.text` is a
  client-visible text view whose completeness depends on `--response-mode` and
  on how the MCP client exposes the envelope.
- Token savings are workload-dependent. The documented fixture savings measure
  repeated operational context, not every prompt or every conversation.
