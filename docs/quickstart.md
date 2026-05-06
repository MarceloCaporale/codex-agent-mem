# Quickstart

This is the shortest path from clone to a working local setup.

## 1. Clone and install

### PowerShell / Windows

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

### bash / macOS / Linux

```bash
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 2. Verify the package

```bash
codex-agent-mem-smoke
```

```powershell
codex-agent-mem-smoke
```

That should insert a sample turn into a local SQLite database and verify retrieval.

## 3. Configure MCP clients

`codex-agent-mem` is an MCP server. The canonical payload is returned in
`structuredContent`; `content.text` is a client-facing textual view controlled by
`--response-mode`.

Start with the installed stdio command:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Recommended defaults:

| Client/runtime | Suggested response mode | Why |
| --- | --- | --- |
| Codex CLI / Codex Desktop | `compact` | Codex can use the structured payload while keeping text short. |
| Claude Code | `compact` | Claude Code exposes useful structured payloads in local MCP calls. |
| Google Gemini CLI | `verbose` if compact only shows one-line summaries | Some client flows do not expose useful `structuredContent` to the model in compact mode. |
| Google Antigravity | Same guidance as Google Gemini CLI when using the same MCP bridge behavior | Use verbose if the agent cannot see the continuity pack content. |

If an agent only sees output like `codex-agent-mem: context_pack ... hash=...`
and not the actual continuity pack, restart that client's MCP bridge with
`--response-mode verbose`.

## 4. Optional Codex config helper

Codex users can generate a ready-to-paste config snippet:

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Paste the generated output into `~/.codex/config.toml`.
The snippet includes MCP tool approvals plus a defensive MCP idle timeout for non-interactive Codex runs.
The default helper emits the `full` profile so writable note, snapshot,
governance, repair, and restore tools are available. Review the approved tools
before pasting if you want a narrower surface.

If you also want automatic `AGENTS.md` reinjection, add `--sync-project-doc` to the `notify` command before `--db-path`.

## 5. Optional local services

Start the inspection API:

```bash
codex-agent-mem-api --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Then open the local inspector:

```text
http://127.0.0.1:37770/ui
```

Start the MCP server:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Use verbose mode for clients that need the payload rendered into `content.text`:

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --response-mode verbose
```

Optional daemon mode is loopback-only in the public `1.0.x` line. Use a local token if you keep it running:

```powershell
codex-agent-mem-daemon --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --profile full --auth-token YOUR_LOCAL_TOKEN
codex-agent-mem-mcp --daemon-url http://127.0.0.1:37773 --daemon-token YOUR_LOCAL_TOKEN
```

Add `--read-only` only for explicit retrieval-only auditing or debugging where
snapshots, policies, inheritance links, repairs, and closure writes must be
blocked.

The local SQLite database is plaintext by default. Treat it as sensitive project data and do not store credentials or API keys in memory.

## 6. Verify continuity-pack reuse

The main token-saving path is incremental reuse. At startup, prefer the
defensive bootstrap tool so broad workspaces do not accidentally load the wrong
thread as active context:

```text
mem_bootstrap_context(
  project_key="YOUR_PROJECT",
  chat_title="optional current chat title",
  current_cwd="optional/current/workdir",
  budget="normal"
)
```

For broad workspaces that contain multiple chats, agents, or parallel client
sessions, `mem_bootstrap_context` may return `context_pack=null` and
`do_not_fetch_project_wide_pack=true`. In that case list persisted sessions
first and pass the selected `session_id` to retrieval tools:

```text
mem_scope_resolve(project_key="YOUR_PROJECT", hint="repo-or-topic")
mem_session_list(project_key="YOUR_PROJECT", limit=20)
mem_session_list(project_key="YOUR_PROJECT", query="repo-or-topic", limit=20)
mem_context_pack(project_key="YOUR_PROJECT", session_id=SESSION_ID, budget="normal")
```

The same optional `session_id` filter is available on read-oriented retrieval tools
such as `mem_search`, `mem_recent`, `mem_project_brief`, `mem_open_work`,
`mem_completion_check`, and `mem_scope_guard`. It filters persisted local memory
inside the `project_key`; it does not add live current-turn awareness.
`mem_session_list` also accepts `query` / `sub_scope_hint` for large broad
workspaces when the agent needs help choosing the right persisted session.
`mem_scope_resolve` is read-only and uses explicit hints only; it does not infer
the live current turn by itself.

If a project-wide pack reports `source_sessions > 1` or
`scope_warning=multi_session_project_scope`, call `mem_session_list(project_key)`
and retry `mem_context_pack(project_key, session_id=...)` before treating the
pack objective as the active thread.

The response includes a `pack_hash`. On the next request, send that hash back.
When you used a session filter, send the same `session_id` too:

```text
mem_context_pack(project_key="YOUR_PROJECT", session_id=SESSION_ID, budget="normal", known_pack_hash="PACK_HASH_FROM_PREVIOUS_CALL")
```

If the continuity pack did not change, the server returns:

```json
{
  "not_modified": true,
  "pack_hash": "PACK_HASH_FROM_PREVIOUS_CALL",
  "message": "continuity pack unchanged"
}
```

This avoids resending unchanged memory. It is most useful after the project has
real repeated context across multiple turns or sessions; a first empty run cannot
save context that does not exist yet.
`known_pack_hash` is scoped to the same project/session retrieval scope used to
build the pack.

## 7. Smoke test with a temporary database

Use a temporary database for install checks instead of a real operational memory
database:

```powershell
$tmp = Join-Path $env:TEMP "codex-agent-mem-smoke.db"
Remove-Item $tmp -ErrorAction SilentlyContinue
codex-agent-mem-smoke --db-path $tmp
Remove-Item $tmp -ErrorAction SilentlyContinue
```

## 8. Rebuild the generated continuity block manually

```bash
codex-agent-mem-refresh-context --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db" --project-key YOUR_PROJECT --cwd /path/to/project
```

```powershell
codex-agent-mem-refresh-context --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --project-key YOUR_PROJECT --cwd C:\Path\To\Project
```

## 9. Run full checks

```powershell
python scripts/smoke_release.py --mcp-subprocess --with-ruff --with-build --with-wheel-smoke
```

The final release gate additionally verifies release checksums against artifacts
built in the same isolated run.
