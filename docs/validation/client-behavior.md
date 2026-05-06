# Client Behavior

MCP clients can expose tool results differently. `codex-agent-mem` therefore
separates the canonical payload from the text shown to the model.

## Canonical payload

`structuredContent` is the canonical machine-readable payload for MCP tool
results.

- Dictionary results are returned as dictionary roots.
- List results are wrapped as `{items, count}` so clients that reject root arrays
  still receive an object root.
- Scalar results are wrapped as `{value}`.
- `mem_context_pack` returns the pack text, stats, operational state, and
  `pack_hash` in `structuredContent`.

Use `structuredContent` for client integrations, automated checks, and any
logic that depends on exact fields.

## Text payload

`content.text` is a text view of the same result. It is controlled by
`--response-mode`:

- `compact`: short summary only.
- `balanced`: short summary plus a note that the complete payload is in
  `structuredContent`.
- `verbose`: JSON-formatted payload in text.

The complete payload is still present in `structuredContent` in all modes, but
some clients do not expose that payload clearly to the model. In those clients,
`verbose` is the practical compatibility mode.

## Google Gemini CLI and Google Antigravity

Use the name `Google Gemini CLI` in public docs and support notes.

For Google Gemini CLI, start with the normal MCP configuration and verify what
the agent can actually read:

1. Call `mem_health_runtime` and confirm the expected `profile`, `read_only`,
   and `response_mode`.
2. Call `mem_bootstrap_context` with the best explicit project/thread/path hint
   available to the host.
3. If it returns `do_not_fetch_project_wide_pack=true`, choose a session/lane
   first and call `mem_context_pack` with explicit `session_id`.
4. If it says the project-wide scope is not broad, compact mode is acceptable.
5. If the agent only sees a one-line summary and not the useful payload, switch
   the MCP command to `--response-mode verbose`.

Apply the same guidance to Google Antigravity when it is configured through the
same MCP bridge surface. Unless a live Antigravity run is recorded, describe
that as configuration guidance rather than direct validation.

## Pack reuse flow

`mem_context_pack` supports an explicit unchanged-pack flow:

Use this after scope is explicit. In broad workspaces, first call
`mem_bootstrap_context` and include `session_id` once a session/lane is
selected.

1. First call:

   ```json
   {
     "project_key": "my-project",
     "session_id": 123,
     "budget": "auto"
   }
   ```

2. Read `structuredContent.pack_hash` from the result.

3. Later call:

   ```json
   {
     "project_key": "my-project",
     "session_id": 123,
     "budget": "auto",
     "known_pack_hash": "previous-pack-hash"
   }
   ```

4. If the pack did not change, the result is:

   ```json
   {
     "not_modified": true,
     "pack_hash": "previous-pack-hash",
     "message": "continuity pack unchanged"
   }
   ```

This avoids resending unchanged continuity packs. It is a continuity/cache
signal, not a security signature.

## Session-aware retrieval

`project_key` remains the primary project/workspace scope. At startup, call
`mem_bootstrap_context(project_key, ...)` when previous state may matter. When
one broad project contains several chats, agents, or client runtimes,
`mem_bootstrap_context` and `mem_scope_resolve` return candidate lanes and
`do_not_fetch_project_wide_pack=true` instead of silently loading a broad pack.
Then call `mem_session_list(project_key, query=...)` and pass the selected
`session_id` to retrieval tools. In large broad workspaces, use `query` or
`sub_scope_hint` on `mem_session_list` as a selection aid before choosing the
`session_id`.

The canonical session metadata is returned in `structuredContent`. The server
also emits compact `content.text` breadcrumbs with `session_filter` and
`source_sessions` lines for `mem_context_pack`. Some clients still summarize or
hide raw `content[0].text`; for those clients, rely on `structuredContent` when
available or use `verbose` during validation/debugging.

When a project-wide context pack spans multiple persisted sessions or inferred
sub-scopes, the server emits `scope_warning=multi_session_project_scope` in
compact text, `structuredContent.stats.scope_warning`, and the textual pack
body. The pack suppresses active-objective selection and recommends
`mem_bootstrap_context` or `mem_session_list + session_id` before the pack is
treated as active context.

`known_pack_hash` is scoped to the same project/session retrieval scope used to
build the pack. Session-aware retrieval filters persisted local memory only; it
does not add live current-turn awareness.

## Client checklist

- Confirm the client can connect to the MCP stdio command.
- Keep normal continuity installs writable when snapshots, closure events, or
  governance writes are expected.
- Use `--read-only` only for explicit retrieval-only auditing or debugging.
- Start with `--profile minimal` for low-impact continuity and `standard` when
  search, provenance, or governance inspection is needed.
- Verify `structuredContent` visibility before assuming compact mode is enough.
- Use `verbose` when the client hides the structured payload from the model.
- Do not claim identical behavior across clients. Record the observed client,
  profile, response mode, date, and evidence level.
