# codex-agent-mem

[![MCP Toplist](https://mcptoplist.com/badge/glama%2FMarceloCaporale%2Fcodex-agent-mem.svg)](https://mcptoplist.com/server/glama%2FMarceloCaporale%2Fcodex-agent-mem)

<p align="center">
  <img src="docs/assets/codex-agent-mem-social-preview.png" alt="codex-agent-mem: persistent local memory for MCP clients" width="100%">
</p>

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/MarceloCaporale/codex-agent-mem)

Other languages: [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [Português do Brasil](./README_PT_BR.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

**Portable, auditable, local-first MCP memory for MCP-compatible AI agents and coding workflows.**

`codex-agent-mem` keeps durable project memory outside the model runtime, compresses continuity into smaller working packs, and carries forward operational state so MCP-compatible AI agents can resume with less repetition, fewer false “done” claims, and more control over what stays in context.

Everything is stored and processed locally by this MCP: SQLite database, FTS index, snapshots, telemetry metadata, and the optional inspector UI. `codex-agent-mem` does not send your memory, project data, prompts, or telemetry to any external server. MCP clients may still expose tool results to the model or service you configure, so treat retrieved memory as local tool output handed to that client.

Born for Codex and GPT workflows, `codex-agent-mem` has grown into a portable MCP memory layer for MCP-compatible runtimes including Codex CLI/Desktop, Claude Code, Google Gemini CLI, Qwen Code workflows using Ollama models, and other local or third-party CLI agent stacks. Validation is tracked per client/runtime and evidence level. Model-specific details stay in the validation docs so the README can describe the public surface without overclaiming one runtime.

`codex-agent-mem` lives locally, keeps memory auditable and pull-based, and does not send your stored memory to any external service.

Public baseline. Built in small, testable slices and still evolving, but already aligned for real use.

## What’s new in v1.0.x

- v1.0.2 fixes a project identity edge case where generated `codex-agent-mem` context inside `AGENTS.md` could be mistaken for active project scope by MCP hosts or agent clients. It also lets manual notes initialize a missing local project record and preserves existing project root metadata on conflicting updates.
- v1.0.1 fixes one local daemon/stdio bridge idle-timeout path that could surface as a false `Transport closed` incident when `--daemon-url` is used.
- v1.0.1 serializes shared request handling inside the optional threaded local daemon so one SQLite-backed server instance is not driven concurrently.
- v1.0.1 hardens the public local-first daemon surface: loopback-only bind validation, optional bearer-token auth for `/mcp`, sanitized `/health`, and token forwarding from the stdio bridge.
- v1.0.1 adds a generated-context instruction-hierarchy guardrail: retrieved memory is advisory project context, not a higher-priority instruction; this is a basic guardrail, not prompt-injection proof.
- v1.0.1 documents that local SQLite memory is plaintext by default in the public 1.0.x line and must not be treated as a secrets vault.
- v1.0.1 normalizes list-returning MCP tool payloads so `structuredContent` uses object roots like `{items, count}` instead of root arrays for stricter clients such as Claude Code.
- v1.0.1 adds session-aware retrieval for persisted memory: `mem_session_list` lists recent sessions, `mem_scope_resolve` ranks persisted lanes from explicit thread/path hints, `mem_bootstrap_context` avoids project-wide startup packs for ambiguous containers, and optional `session_id` filters retrieval tools so broad project scopes do not mix chats or agents. Project-wide packs that span multiple sessions or inferred sub-scopes emit a visible scope warning and recommend narrowing first. This is not live current-turn awareness.
- v1.0.1 keeps normal continuity installs writable by default; `--read-only` is an explicit retrieval-only audit/debug mode, not the default operating mode.

- low-impact MCP runtime profiles: `minimal`, `standard`, and `full`
- explicit `--read-only` audit/debug mode that blocks mutating tools and avoids closure writes
- lazy SQLite initialization so unused MCP connections stay cheap
- compact MCP responses by default, with full payloads kept in `structuredContent`
- `known_pack_hash` / `not_modified` support so unchanged continuity packs are not resent
- runtime heartbeat diagnostics, spawn-storm warning, optional telemetry, and an optional daemon/stdio bridge

Latest releases: [v1.0.2 Identity + Scope Patch](./CHANGELOG.md#102---2026-05-07) | [v1.0.1 Transport + Local Security Hotfix](./CHANGELOG.md#101---prepared-2026-05-06) | [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21)

## Snapshot (synthetic v1.0 fixtures)

| Scenario | Profile | Source tokens | Pack tokens | Saved | `not_modified` | Tools | Lazy init | Read-only |
|---|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | `minimal` | 1,841 | 253 | 86.26% | true | 4 | false->true | true |
| Medium agent workflow | `minimal` | 4,855 | 270 | 94.44% | true | 4 | false->true | true |
| Large repeated audit | `minimal` | 9,731 | 269 | 97.24% | true | 4 | false->true | true |
| Sub-agent handoff example | `minimal` | 6,523 | 276 | 95.77% | true | 4 | false->true | true |

Across these reproducible fixtures, repeated operational context was reduced from ~22,950 source tokens to ~1,068 memory-pack tokens, an approximate 95.35% reduction. This is not a universal guarantee; it shows the effect when an agent would otherwise resend the same project continuity.

`Tools=4` refers to the pre-session-aware `minimal` profile used by these fixtures. In v1.0.1, `minimal` also includes `mem_session_list`, `mem_scope_resolve`, and `mem_bootstrap_context`, and the `standard` profile exposes 20 tools for broader retrieval, governance, and audit workflows.

### Runtime validation snapshot

| Runtime | Setup | Observed metrics | Result |
|---|---|---|---|
| Writable MCP default | Codex/Gemini/Claude local daemon bridges, `read_only=false`; `full` where writable tools are required | `mem_note_create` wrote indexed manual notes and `mem_search` / `mem_context_pack` recovered them; `mem_snapshot_create(project_key, label, session_id)` recorded high-confidence provenance | Writable manual-note and snapshot-provenance smokes passed |
| Codex Desktop | Codex Desktop, MCP stdio, explicit retrieval-only `minimal`, `read-only`, `compact` synthetic v1.0 fixtures | ~22,950 source tokens -> ~1,068 pack tokens, ~95.35% repeated-context reduction, `not_modified=true` on repeated packs | Retrieval-only MCP validation plus public reproducible verification; writable continuity is covered by the writable default row |
| Codex CLI / `codex exec` | Codex CLI MCP stdio path, short-lived / ephemeral execution | same local MCP server and config style as Desktop; short-lived CLI lifecycle validated separately from the long-lived Desktop host behavior | Validated Codex CLI path |
| Google Gemini CLI | `codex-agent-mem` MCP stdio, explicit retrieval-only `standard`, `read-only`; `compact` when structured payloads are visible, otherwise `verbose` | stable process, request counter increased as expected, object-root payloads verified where visible | Retrieval-only MCP validation with client-exposure caveat |
| Claude Code | Claude Opus 4.7, `codex-agent-mem` MCP stdio only, explicit retrieval-only `standard`, `read-only`, `compact` | requests `3 -> 8`, lazy init `false -> true`, `same_db_process_count=2` with one Claude Code host active, `spawn_storm_warning=false`, `mem_search count=2` | Retrieval-only MCP validation passed |
| Qwen Code | Qwen Code 0.15.0, local Ollama, `qwen3.6:latest`, explicit retrieval-only `standard`, `read-only`, `compact` | real MCP calls to `mem_context_pack`, `mem_search`, `mem_open_work`, `mem_completion_check`, `mem_health_runtime`; requests `8`, lazy init `true`, `spawn_storm_warning=false`, `not_modified=true` | Retrieval-only local MCP validation passed |
| Qwen local model smokes | Qwen Code 0.15.0 with Ollama models `qwen3.6:35b-a3b-q8_0` and `qwen3.5:9b` | both models answered CLI smoke tests and invoked `mem_health_runtime` through MCP stdio; retrieval-only `read_only=true`, clean `stdin_eof` exits | Retrieval-only local model smokes passed |
| DeepSeek-V3.2 | Qwen Code 0.15.0, `deepseek-v3.2:cloud` through Ollama Cloud, explicit retrieval-only `standard`, `read-only`, `compact` | real MCP calls to `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `spawn_storm_warning=false`, `not_modified=true` | Retrieval-only cloud-backed MCP validation passed |
| Minimax M2.5 | Qwen Code 0.15.0, `minimax-m2.5:cloud` through Ollama Cloud, explicit retrieval-only `standard`, `read-only`, `compact` | real MCP calls to `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `not_modified=true` | Retrieval-only cloud-backed MCP validation passed |
| Kimi Code CLI | Kimi Code CLI 1.38.0, `codex-agent-mem` MCP stdio, explicit retrieval-only `standard`, `read-only`, `compact` | `kimi mcp test codex-agent-mem` connected and listed the expected standard-profile tools; Kimi K2.5 / Kimi K2.6 full model tool-call validation remains in continuous evaluation | Retrieval-only MCP connection validated; model-run validation not claimed |
| Grok / xAI | Protocol-level compatibility note | MCP stdio / JSON-RPC protocol behavior reviewed | Protocol note |

Grok / xAI is listed as a protocol-level compatibility note, not live model tool-call validation. The live validated rows are the MCP client/model pairs measured directly: Codex Desktop/CLI, Google Gemini CLI, Claude Code, Qwen Code, Qwen local model smokes, DeepSeek-V3.2 through Ollama Cloud, Minimax M2.5 through Ollama Cloud, and Kimi Code CLI connection validation. More generally, `codex-agent-mem` is model-agnostic at the MCP layer; new pairs are added as their live measurements are captured.

## Verifiable Results

`codex-agent-mem` includes a reproducible verification sandbox and a public evidence export for v1.0.0. The fixture approach is intentional: the MCP optimizes repeatable operational-context handling, so the public evidence keeps the repeated context controlled instead of turning the benchmark into a different conversation every run.

The public v1.0.x evidence combines reproducible verification fixtures with live MCP runtime validation across the runtimes listed above. It reports context compression, repeated-pack avoidance with `known_pack_hash`, lazy initialization, minimal tool surface, explicit read-only mode safety, response diet, local telemetry, closure control, and a sub-agent handoff example.

See: [Verification Evidence](./docs/verification/) and [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md).

## Claude Code and claude-mem

`codex-agent-mem` runs in Claude Code as a standard MCP stdio server. It does not install session-start hooks, stop hooks, or automatic post-turn summarization. Memory is retrieved on demand through MCP tools such as `mem_context_pack`, `mem_search`, `mem_open_work`, and `mem_completion_check`.

If you already use `claude-mem`, both tools can technically coexist. For lower-overhead, lower-latency workflows, use one active memory layer at a time. In local validation with one Claude Code host active, `codex-agent-mem` alone kept the runtime compact (`same_db_process_count=2`, `spawn_storm_warning=false`). Running it alongside `claude-mem` increased visible tool surface to 61 tools, added a session-start memory block of about 6,995 tokens, and showed post-turn stop-hook delays. This does not break `codex-agent-mem`, but it makes results harder to compare and can increase overhead and latency.

Use `codex-agent-mem` when you prefer local-first, auditable, pull-based memory with explicit retrieval and deterministic closure checks. Use additional memory plugins only when you intentionally want their automatic hook-based behavior.

For token-sensitive Claude Code workflows, `codex-agent-mem` is designed for low overhead by default: no session-start injection, no stop-hook summarization, compact responses, explicit budgets, and `pack_hash` / `not_modified` short-circuiting for unchanged packs.

## Optional companion: clean-process-ended

`codex-agent-mem` v1.0.1 and `clean-process-ended` ([GitHub](https://github.com/MarceloCaporale/clean-process-ended)) v0.7.2 work independently, but they solve adjacent problems in local agent workflows.

- `codex-agent-mem` preserves continuity: project memory, scoped context packs, manual notes, snapshots, open work, blockers, and deterministic closure checks.
- `clean-process-ended` handles local process hygiene: ownership-first diagnostics, dry-run close checks, and compact janitor receipts.

Together they improve end-of-task workflows: recover context, finish the work, check local process state, and store compact close evidence without making either MCP a hard dependency of the other.

## What you get

### Continuity

- **Compact continuity, not raw replay**: turns repeated session context into smaller `AGENTS.md` working packs when compression is actually favorable
- **Operational state across sessions and agents**: keeps objective, constraints, pending work, blockers, Definition of Done, and scope guardrails visible and reusable so context is not captive to one model, one session, or one provider UI
- **MCP-native integration**: runs as a local MCP stdio server for Codex, Claude Code, Google Gemini CLI, Qwen Code, and other MCP-compatible clients; Codex `notify` and optional `AGENTS.md` sync remain available where useful
- **Token efficiency for agent workflows**: improves the token economy of repeated agent work by reducing continuity replay when the compact pack wins; the public v1.0 fixtures show 86% to 97% reduction on repeated-context scenarios

### Closure Control

- **Deterministic closure control**: exposes `mem_open_work` and `mem_completion_check` so open work beats stale completion claims
- **Scope retention**: carries forward must-not-drop continuity, recent changes, and active blockers instead of only decisions

### Governance and Audit

- **Governed memory selection**: applies project policies, inheritance rules, and repair events instead of mixing everything blindly
- **Inspectable MCP memory**: the local `/ui` lets you navigate recent changes, scope guard, provenance, health, snapshots, governance state, and stored memory without opening the SQLite database by hand
- **Fully local and auditable**: SQLite + FTS5, provenance, health diagnostics, snapshots, and a local inspector UI with no external memory service and no outbound memory sync
- **Clear local security boundary**: v1.0.1 hardens loopback daemon access, optional bearer-token auth, sanitized health output, and generated-context instruction hierarchy; this is not prompt-injection proof, and the public 1.0.x SQLite database remains plaintext by default and should not be used as a secrets vault

Key docs: [AGENTS.md](./AGENTS.md) | [Quickstart](./docs/quickstart.md) | [Codex Integration](./docs/codex-integration.md) | [Codex Desktop Note](./docs/codex-desktop-lifecycle-note.md) | [Support Matrix](./docs/support-matrix.md) | [Design Decisions](./docs/design-decisions.md)

Built for long audits, multi-step project continuity, and workflows where the real failure mode is not only forgetting decisions, but also dropping scope, losing blockers, and declaring completion too early.

## Status

`1.0.2` is the current 1.0.x maintenance release. `1.0.0` remains the public verification baseline for the reproducible metrics below.

What works today:

- Codex `notify` ingestion on `agent-turn-complete`
- local SQLite persistence with FTS5
- heuristic extraction of `session_summary`, `decision`, `objective`, `constraint`, `pending_item`, `completed_item`, `blocker`, and `completion_claim`
- hierarchical Definition of Done tracking across `project_dod`, `mission_dod`, and `session_dod`
- generated working-memory packs with approximate token budget and compression stats
- budgeted packs for `micro`, `normal`, and `full` reinjection
- opt-in `AGENTS.md` sync through `--sync-project-doc` when the generated pack is smaller than the source context
- operational-state carry-forward so the next run can recover objective, pending work, blockers, and scope guardrails
- deterministic closure control with `mem_open_work` and `mem_completion_check`
- recent-change deltas through `mem_recent_changes`
- scope continuity and must-not-drop guardrails through `mem_scope_guard`
- false-completion guardrails that keep “done” from overriding open work when pending items, blockers, or DoD gaps still exist
- context sync and closure metrics persisted per project
- automatic budget selection for context packs when `budget=auto`
- memory provenance persisted per observation and queryable through `mem_provenance`
- diagnostic health reporting through `mem_health`
- MCP runtime diagnostics through `mem_health_runtime`
- manual operational notes through `mem_note_create`, indexed for `mem_search` and eligible for `mem_context_pack`
- versioned project snapshots through `mem_snapshot_create`, `mem_snapshot_list`, and `mem_snapshot_restore`
- governed memory policies through `mem_policy_validate`, `mem_policy_add`, `mem_policy_list`, and `mem_policy_remove`
- selective inheritance links through `mem_inheritance_add`, `mem_inheritance_list`, and `mem_inheritance_remove`
- governed repair proposals and derived repair events through `mem_repair_propose` and `mem_repair_apply`
- low-impact MCP profiles through `--profile minimal|standard|full`
- explicit read-only audit/debug mode through `--read-only`
- compact MCP response text with full `structuredContent`
- `known_pack_hash` / `not_modified` continuity-pack reuse
- short in-process caching for expensive read tools
- lazy SQLite initialization for cheap unused MCP connections
- enriched runtime health with profile, mutability, cache, lazy-init, heartbeat, and spawn-storm diagnostics
- optional local runtime telemetry through `--telemetry-mode off|summary|debug`
- optional local daemon through `codex-agent-mem-daemon` and stdio bridge mode with `--daemon-url`
- FastAPI inspection API
- local inspection UI at `/ui`, including recent changes, scope guard, provenance, health, snapshots, and governance state
- local policy CLI with `codex-agent-mem-policy`
- MCP stdio server with:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_session_list`
  - `mem_scope_resolve`
  - `mem_bootstrap_context`
  - `mem_project_brief`
  - `mem_open_work`
  - `mem_completion_check`
  - `mem_recent_changes`
  - `mem_scope_guard`
  - `mem_context_pack`
  - `mem_provenance`
  - `mem_health`
  - `mem_health_runtime`
  - `mem_snapshot_list`
  - `mem_note_create`
  - `mem_snapshot_create`
  - `mem_snapshot_restore`
  - `mem_policy_list`
  - `mem_policy_validate`
  - `mem_policy_add`
  - `mem_policy_remove`
  - `mem_inheritance_list`
  - `mem_inheritance_add`
  - `mem_inheritance_remove`
  - `mem_repair_propose`
  - `mem_repair_apply`
- automated tests

What is intentionally not in scope yet:

- embeddings
- vector stores
- Codex App Server ingestion
- Codex hooks adapter
- Ollama adapter
- multi-agent orchestration

## Why this repository exists

- Agent workflows often need durable context that stays outside one runtime process.
- Retrieval alone does not solve the bigger failure mode: losing scope and forcing the user to restate prior context.
- A compressed continuity block or MCP context pack can reduce how much prior context must be replayed manually.
- Carrying only decisions is not enough; the runtime also needs active objective, open work, blockers, and a rule against false closure.
- SQLite keeps the implementation local-first, auditable, and easy to inspect.
- The current release intentionally focuses on a narrow, testable slice rather than a broad unfinished platform.
- Long-lived and short-lived MCP hosts can behave differently under runtime load; see the validation docs for the exact runtime boundary.

## Installation model

`codex-agent-mem` is installed as a local Python package and exposed to MCP-compatible clients through stdio commands.

The stable pattern is:

1. install the package
2. point the MCP client at the installed command
3. keep the memory database local and auditable

Codex-specific `notify` and `mcp_servers` snippets are generated by `codex-agent-mem-bootstrap-codex`; other MCP clients use their own configuration files.

## Quickstart

If you want the shortest path from clone to a working local setup:

### PowerShell / Windows

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### bash / macOS / Linux

```bash
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

For Codex, paste the generated snippet into `~/.codex/config.toml`. For other MCP clients, use the common stdio command in [Configure MCP clients](#configure-mcp-clients).

## Install

### Option A: `pipx` from GitHub

Install directly from the repository URL:

```bash
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

### Option B: local development install

```bash
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

## Configure MCP clients

The MCP server entry point is the same for every compatible client:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Point your MCP-capable client at that installed stdio command. The validated public v1.0.x paths include Codex CLI/Desktop, Claude Code, Google Gemini CLI, Qwen Code with local Qwen models through Ollama, DeepSeek-V3.2 and Minimax M2.5 through Ollama Cloud, plus Kimi Code CLI connection validation.

### Codex helper

Generate a ready-to-paste snippet:

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

For Codex, that prints the `notify` block, the `[mcp_servers."codex-agent-mem"]` block, an explicit stdio idle-timeout, and MCP tool approvals you can paste into `~/.codex/config.toml`.

For long-lived Codex Desktop sessions, prefer a longer MCP idle timeout such as `--idle-timeout-seconds 1800` so the Desktop thread is less likely to keep a closed stdio transport. For short CLI or `codex exec` runs, `300` seconds is usually enough and keeps cleanup faster.

Automatic `AGENTS.md` reinjection is now opt-in. Add `--sync-project-doc` to the `notify` command only if you want generated working-memory blocks written back into the working directory.

## How agents should use it

Once configured, the agent should use `codex-agent-mem` proactively when continuity matters. You should not need to repeat "use the memory MCP" every few turns.

Recommended pattern:

- start with `mem_bootstrap_context` when prior decisions, pending work, blockers, constraints, or project state may matter; pass thread, chat-title, cwd, or repo hints when the host exposes them
- call `mem_context_pack` directly only when the scope is already explicit, preferably with `session_id` for broad workspaces
- pass `known_pack_hash` on repeated checks so unchanged packs return `not_modified` instead of resending context
- use `mem_search` only when the compact pack is not enough
- before claiming done, call `mem_open_work` and `mem_completion_check` for implementation, validation, publishing, migration, or documentation tasks

This is where the practical token economy comes from: compact continuity first, targeted expansion only when needed, and no repeated pack when nothing changed.

Example files live under [examples/codex](./examples/codex/), with Ollama workflow notes under [examples/ollama](./examples/ollama/).

## Run locally

Start the inspection API:

```bash
codex-agent-mem-api --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Then open:

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

The current MCP transport is stdio. That means one process per host connection is normal; it is not a singleton daemon. The defensive idle timeout is there to let unused or orphaned instances exit cleanly.

Recommended defaults: use a longer timeout for Codex Desktop sessions, for example `1800` seconds, and a shorter timeout for CLI/ephemeral runs, for example `300` seconds.

Manually rebuild the generated continuity block for one directory:

```bash
codex-agent-mem-refresh-context --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db" --project-key YOUR_PROJECT --cwd /path/to/project
```

```powershell
codex-agent-mem-refresh-context --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --project-key YOUR_PROJECT --cwd C:\Path\To\Project
```

## Quick verification

Run the smoke test:

```bash
codex-agent-mem-smoke --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

That inserts a sample turn, extracts observations, and verifies recent retrieval and project brief generation.

## Token efficiency: what saves tokens now

- The package compiles a smaller working-memory pack from recent turns, durable decisions, and derived operational state.
- When `--sync-project-doc` is enabled and that pack is actually smaller than the source context, it is synced into `AGENTS.md` for the working directory.
- MCP retrieval and optional `AGENTS.md` sync let future sessions start with compressed continuity instead of forcing you to restate old scope.
- `mem_context_pack` exposes the same compact pack over MCP for on-demand retrieval.
- The pack now carries forward pending work and blockers, so a future run can recover “what remains” instead of only “what was decided.”

This is token efficiency for agent workflows, not magic compression. `codex-agent-mem` improves the token economy by reducing repeated project context, reusing unchanged packs through `known_pack_hash`, and letting agents expand only the memory they need.

## Approximate token savings

In plain language: this usually aims to cut down the amount of repeated context you have to replay, not to eliminate it completely.

What we can say honestly from local validation:

- the public v1.0 fixtures reduced repeated context from ~22,950 source tokens to ~1,068 memory-pack tokens, about `95.35%` in that controlled scenario
- individual repeated-context scenarios in the fixture suite landed between `86%` and `97%` reduction
- live runtime checks confirmed compact MCP retrieval, stable process lifecycle, object-root/no-reinjection behavior where visible, and writable snapshot provenance for local Codex/Gemini/Claude daemon bridges

Examples from the public v1.0 verification sandbox:

- `1,841 -> 253` approximate tokens
- `4,855 -> 270` approximate tokens
- `9,731 -> 269` approximate tokens
- `6,523 -> 276` approximate tokens

Important: this is not a fixed guarantee per prompt. If the compact pack is not actually smaller than the source context, `codex-agent-mem` skips reinjection instead of pretending it saved tokens.

## What this helps catch now

- losing the original objective after a few runs
- silently narrowing scope when the user asked for more
- declaring completion while pending work still exists
- forgetting blockers and re-entering the next run as if the task were finished

## Repository layout

- [src/codex_agent_mem](./src/codex_agent_mem/) - package code
- [tests](./tests/) - executable tests
- [examples/codex](./examples/codex/) - Codex integration examples
- [examples/ollama](./examples/ollama/) - Ollama workflow notes
- [scripts](./scripts/) - local bootstrap helpers
- [docs](./docs/) - architecture, integration, quickstart, and release notes

## Documentation map

- [AGENTS.md](./AGENTS.md) - repo map and operational guide for MCP-compatible AI agents
- [docs/quickstart.md](./docs/quickstart.md) - shortest install and first-run path
- [docs/codex-integration.md](./docs/codex-integration.md) - how notify and MCP fit into Codex
- [docs/verification](./docs/verification/) - reproducible public metrics and v1.0.0 evidence
- [docs/support-matrix.md](./docs/support-matrix.md) - current support and known gaps
- [docs/codex-desktop-lifecycle-note.md](./docs/codex-desktop-lifecycle-note.md) - observed Codex Desktop lifecycle behavior and practical mitigations
- [docs/design-decisions.md](./docs/design-decisions.md) - explicit product and architecture decisions
- [docs/architecture.md](./docs/architecture.md) - portable technical architecture of the current release
- [docs/validation](./docs/validation/) - validation levels, runtime support, client behavior, and public evidence notes
- [CONTRIBUTING.md](./CONTRIBUTING.md) - contribution workflow and quality bar
- [SECURITY.md](./SECURITY.md) - support scope and security reporting guidance
- [docs/discoverability.md](./docs/discoverability.md) - recommended GitHub description, topics, and release framing

## Release surface

This repository includes:

- clean root package layout
- installable `pyproject.toml`
- command entry points
- tests
- CI workflow
- license
- changelog

## Author

Created and maintained by Marcelo Caporale.

- X: [@MarceloCaporale](https://x.com/MarceloCaporale)
- Studio: [Visual AI Media](https://visualaimedia.com)
- Lab: [Visual Systems Lab](https://visualsystemslab.com)
