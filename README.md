# codex-agent-mem

Other languages: [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

**Portable, auditable, local-first MCP continuity layer for Codex, Claude, local coding agents, and third-party CLI workflows.**

`codex-agent-mem` keeps durable project memory outside the model runtime, compresses continuity into smaller working packs, and carries forward operational state so Codex can resume with less repetition, fewer false “done” claims, and more control over what stays in context.

Everything is stored and processed locally by this MCP: SQLite database, FTS index, snapshots, telemetry metadata, and the optional inspector UI. `codex-agent-mem` does not send your memory, project data, prompts, or telemetry to any external server.

Born for Codex and GPT-5.x workflows, `codex-agent-mem` has grown into a portable MCP memory layer for MCP-compatible agent runtimes such as Codex CLI, Codex Desktop, Gemini CLI with Gemini 3.1 Pro, Claude Code with Opus 4.7 or Sonnet 4.6, Qwen Code with local Qwen 3.6 / Qwen 3.5 models through Ollama, DeepSeek-V3.2 and Minimax M2.5 through Ollama Cloud, and custom local agent stacks. Continuous evaluation: Kimi Code CLI, GLM-5, Kimi K2.5, and Kimi K2.6. Kimi Code CLI connects to the `codex-agent-mem` MCP server through stdio; full live model tool-call validation is tracked separately before being claimed. It has also been externally audited for protocol-level compatibility with Grok / xAI and DeepSeek-style MCP orchestrators.

`codex-agent-mem` lives locally, keeps memory auditable and pull-based, and does not send your stored memory to any external service.

Scope distinction: Codex CLI and Codex Desktop validation is not ChatGPT web/app connector validation, and Claude Code validation is not Claude web / claude.ai validation. ChatGPT web/app and Claude web are tracked as separate future integration surfaces, not as v1.0 validated runtimes.

Public baseline. Built in small, testable slices and still evolving, but already aligned for real use.

## What’s new in v1.0.0

- low-impact MCP runtime profiles: `minimal`, `standard`, and `full`
- real `--read-only` mode that blocks mutating tools and avoids closure writes
- lazy SQLite initialization so unused MCP connections stay cheap
- compact MCP responses by default, with full payloads kept in `structuredContent`
- `known_pack_hash` / `not_modified` support so unchanged continuity packs are not resent
- runtime heartbeat diagnostics, spawn-storm warning, optional telemetry, and an optional daemon/stdio bridge

Latest releases: [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Snapshot (synthetic v1.0 fixtures)

| Scenario | Profile | Source tokens | Pack tokens | Saved | `not_modified` | Tools | Lazy init | Read-only |
|---|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | `minimal` | 1,841 | 216 | 88.27% | true | 4 | false->true | true |
| Medium agent workflow | `minimal` | 4,855 | 233 | 95.20% | true | 4 | false->true | true |
| Large repeated audit | `minimal` | 9,731 | 232 | 97.62% | true | 4 | false->true | true |
| Sub-agent handoff example | `minimal` | 6,523 | 239 | 96.34% | true | 4 | false->true | true |

Across these reproducible fixtures, repeated operational context was reduced from ~22,950 source tokens to ~920 memory-pack tokens, an approximate 96.0% reduction. This is not a universal guarantee; it shows the effect when an agent would otherwise resend the same project continuity.

`Tools=4` refers to the `minimal` profile used by these fixtures. The `standard` profile exposes 17 tools for broader retrieval, governance, and audit workflows.

### Runtime validation snapshot

| Runtime | Setup | Observed metrics | Result |
|---|---|---|---|
| Codex Desktop | Codex Desktop using GPT-5.4 in this Codex environment, reasoning effort xhigh, synthetic v1.0 fixtures | ~22,950 source tokens -> ~920 pack tokens, ~96.0% repeated-context reduction, `not_modified=true` on repeated packs | Public reproducible verification |
| Codex CLI / `codex exec` | Codex CLI MCP stdio path, short-lived / ephemeral execution | same local MCP server and config style as Desktop; short-lived CLI lifecycle validated separately from the long-lived Desktop host behavior | Validated Codex CLI path |
| Gemini CLI | Gemini 3.1 Pro, `codex-agent-mem` MCP stdio, `standard`, `read-only`, `compact` | stable process, request counter increased as expected, `mem_search` returned object root `{items, count}` with `count=2` | Live MCP validation passed |
| Claude Code | Claude Opus 4.7, `codex-agent-mem` MCP stdio only, `standard`, `read-only`, `compact` | requests `3 -> 8`, lazy init `false -> true`, `same_db_process_count=2` with one Claude Code host active, `spawn_storm_warning=false`, `mem_search count=2` | Live MCP validation passed |
| Qwen Code | Qwen Code 0.15.0, local Ollama, `qwen3.6:latest`, `standard`, `read-only`, `compact` | real MCP calls to `mem_context_pack`, `mem_search`, `mem_open_work`, `mem_completion_check`, `mem_health_runtime`; requests `8`, lazy init `true`, `spawn_storm_warning=false`, `not_modified=true` | Live local MCP validation passed |
| Qwen local model smokes | Qwen Code 0.15.0 with Ollama models `qwen3.6:35b-a3b-q8_0` and `qwen3.5:9b` | both models answered CLI smoke tests and invoked `mem_health_runtime` through MCP stdio; requests `4`, `read_only=true`, clean `stdin_eof` exits | Live local model smokes passed |
| DeepSeek-V3.2 | Qwen Code 0.15.0, `deepseek-v3.2:cloud` through Ollama Cloud, `standard`, `read-only`, `compact` | real MCP calls to `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `spawn_storm_warning=false`, `not_modified=true` | Live cloud-backed MCP validation passed |
| Minimax M2.5 | Qwen Code 0.15.0, `minimax-m2.5:cloud` through Ollama Cloud, `standard`, `read-only`, `compact` | real MCP calls to `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `not_modified=true` | Live cloud-backed MCP validation passed |
| Kimi Code CLI | Kimi Code CLI 1.38.0, `codex-agent-mem` MCP stdio, `standard`, `read-only`, `compact` | `kimi mcp test codex-agent-mem` connected and listed 17 tools; Kimi K2.5 / Kimi K2.6 full model tool-call validation remains in continuous evaluation | MCP connection validated; model-run validation not claimed |
| Grok / xAI | External model/runtime audit; no local Grok CLI available | protocol-compatible through an MCP stdio-capable orchestrator or a thin JSON-RPC stdio wrapper | Externally audited; not live-local validated |

Grok is an external audit, not a local live CLI session on this machine. Qwen Code is locally validated with Ollama-backed models and MCP stdio. DeepSeek-V3.2 and Minimax M2.5 are live-validated through Ollama Cloud-backed models, not local inference. Kimi Code CLI is MCP-connected, while Kimi K2.5 / Kimi K2.6 model-level validation is still tracked as continuous evaluation because the full models are large and require a separate runtime path. More generally, `codex-agent-mem` is model-agnostic at the MCP layer; the table lists model/runtime pairs already measured live, and new pairs are added as their live measurements are captured. For hosts without a native MCP client, the expected integration path is a thin JSON-RPC stdio wrapper or an MCP-capable orchestrator.

## Verifiable Results

`codex-agent-mem` includes a reproducible verification sandbox and a public evidence export for v1.0.0.

The current public run was executed with **Codex Desktop using GPT-5.4 in this Codex environment, reasoning effort xhigh** on synthetic fixtures. It reports context compression, repeated-pack avoidance with `known_pack_hash`, lazy initialization, minimal tool surface, read-only safety, response diet, local telemetry, closure control, and a sub-agent handoff example. This is a Codex Desktop validation, not a ChatGPT web/app connector validation.

See: [Verification Evidence](./docs/verification/) and [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md).

## Claude Code and claude-mem

`codex-agent-mem` runs in Claude Code as a standard MCP stdio server. It does not install session-start hooks, stop hooks, or automatic post-turn summarization. Memory is retrieved on demand through MCP tools such as `mem_context_pack`, `mem_search`, `mem_open_work`, and `mem_completion_check`.

If you already use `claude-mem`, both tools can technically coexist. For lower-overhead, lower-latency workflows, use one active memory layer at a time. In local validation with one Claude Code host active, `codex-agent-mem` alone kept the runtime compact (`same_db_process_count=2`, `spawn_storm_warning=false`). Running it alongside `claude-mem` increased visible tool surface to 61 tools, added a session-start memory block of about 6,995 tokens, and showed post-turn stop-hook delays. This does not break `codex-agent-mem`, but it makes results harder to compare and can increase overhead and latency.

Use `codex-agent-mem` when you prefer local-first, auditable, pull-based memory with explicit retrieval and deterministic closure checks. Use additional memory plugins only when you intentionally want their automatic hook-based behavior.

For token-sensitive Claude Code workflows, `codex-agent-mem` is designed to be cheap by default: no session-start injection, no stop-hook summarization, compact responses, explicit budgets, and `pack_hash` / `not_modified` short-circuiting for unchanged packs.

## What you get

### Continuity

- **Compact continuity, not raw replay**: turns repeated session context into smaller `AGENTS.md` working packs when compression is actually favorable
- **Operational state that survives sessions**: keeps objective, constraints, pending work, blockers, Definition of Done, and scope guardrails visible and reusable
- **Codex-native integration**: built around `notify`, MCP stdio, optional `AGENTS.md` sync, and defensive runtime cleanup for real Codex workflows
- **Practical token savings**: reduces repeated continuity replay when the compact pack wins; the public v1.0 fixtures show 88% to 97% reduction on repeated-context scenarios

### Closure Control

- **Deterministic closure control**: exposes `mem_open_work` and `mem_completion_check` so open work beats stale completion claims
- **Scope retention**: carries forward must-not-drop continuity, recent changes, and active blockers instead of only decisions

### Governance and Audit

- **Governed memory selection**: applies project policies, inheritance rules, and repair events instead of mixing everything blindly
- **Fully local and auditable**: SQLite + FTS5, provenance, health diagnostics, snapshots, and a local inspector UI with no external memory service and no outbound memory sync

Key docs: [AGENTS.md](./AGENTS.md) | [Quickstart](./docs/quickstart.md) | [Codex Integration](./docs/codex-integration.md) | [Codex Desktop Note](./docs/codex-desktop-lifecycle-note.md) | [Support Matrix](./docs/support-matrix.md) | [Design Decisions](./docs/design-decisions.md)

Built for long audits, multi-step project continuity, and workflows where the real failure mode is not only forgetting decisions, but also dropping scope, losing blockers, and declaring completion too early.

## Status

`1.0.0` is the current baseline release.

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
- versioned project snapshots through `mem_snapshot_create`, `mem_snapshot_list`, and `mem_snapshot_restore`
- governed memory policies through `mem_policy_validate`, `mem_policy_add`, `mem_policy_list`, and `mem_policy_remove`
- selective inheritance links through `mem_inheritance_add`, `mem_inheritance_list`, and `mem_inheritance_remove`
- governed repair proposals and derived repair events through `mem_repair_propose` and `mem_repair_apply`
- low-impact MCP profiles through `--profile minimal|standard|full`
- read-only MCP mode through `--read-only`
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

- Codex workflows often need durable context that stays outside the runtime.
- Retrieval alone does not solve the bigger failure mode: losing scope and forcing the user to restate prior context.
- A compressed continuity block that Codex loads automatically can reduce how much prior context must be replayed manually.
- Carrying only decisions is not enough; the runtime also needs active objective, open work, blockers, and a rule against false closure.
- SQLite keeps the implementation local-first, auditable, and easy to inspect.
- The current release intentionally focuses on a narrow, testable slice rather than a broad unfinished platform.
- Codex Desktop and `codex exec --ephemeral` do not currently behave the same way under long-lived MCP load; see the diagnostic note if you need the exact runtime boundary.

## Important expectation

Codex does not currently install arbitrary MCP tools from a GitHub URL in one step.

The supported path is still:

1. install the Python package
2. point Codex `notify` and `mcp_servers` at the installed commands

This repository is prepared so that workflow is clean and repeatable.

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

Then paste the generated snippet into `~/.codex/config.toml`.

## Install

### Option A: `pipx` from GitHub

Install directly from the repository URL:

```bash
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
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

## Configure Codex

Generate a ready-to-paste snippet:

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

That prints the `notify` block, the `[mcp_servers."codex-agent-mem"]` block, an explicit stdio idle-timeout, and read-only MCP tool approvals you can paste into `~/.codex/config.toml`.

For long-lived Codex Desktop sessions, prefer a longer MCP idle timeout such as `--idle-timeout-seconds 1800` so the Desktop thread is less likely to keep a closed stdio transport. For short CLI or `codex exec` runs, `300` seconds is usually enough and keeps cleanup faster.

Automatic `AGENTS.md` reinjection is now opt-in. Add `--sync-project-doc` to the `notify` command only if you want generated working-memory blocks written back into the working directory.

## How agents should use it

Once configured, the agent should use `codex-agent-mem` proactively when continuity matters. You should not need to repeat "use the memory MCP" every few turns.

Recommended pattern:

- start with `mem_context_pack` when prior decisions, pending work, blockers, constraints, or project state may matter
- pass `known_pack_hash` on repeated checks so unchanged packs return `not_modified` instead of resending context
- use `mem_search` only when the compact pack is not enough
- before claiming done, call `mem_open_work` and `mem_completion_check` for implementation, validation, publishing, migration, or documentation tasks

This is where the practical token savings come from: compact continuity first, targeted expansion only when needed, and no repeated pack when nothing changed.

Example files also live under [examples/codex](./examples/codex/).

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

## What saves tokens now

- The package compiles a smaller working-memory pack from recent turns, durable decisions, and derived operational state.
- When `--sync-project-doc` is enabled and that pack is actually smaller than the source context, it is synced into `AGENTS.md` for the working directory.
- Codex loads `AGENTS.md` before the user prompt, so future sessions can start with compressed continuity instead of forcing you to restate old scope.
- `mem_context_pack` exposes the same compact pack over MCP for on-demand retrieval.
- The pack now carries forward pending work and blockers, so a future run can recover “what remains” instead of only “what was decided.”

## Approximate token savings

In plain language: this usually aims to cut down the amount of repeated context you have to replay, not to eliminate it completely.

What we can say honestly from local validation:

- the public v1.0 fixtures reduced repeated context from ~22,950 source tokens to ~920 memory-pack tokens, about `96.0%` in that controlled scenario
- individual repeated-context scenarios in the fixture suite landed between `88%` and `97%` reduction
- live runtime checks in Gemini CLI, Claude Code, Qwen Code, DeepSeek-V3.2 through Ollama Cloud, and Minimax M2.5 through Ollama Cloud confirmed compact MCP retrieval, stable process lifecycle, read-only mode, and object-root/no-reinjection behavior where visible

Examples from the public v1.0 verification sandbox:

- `1,841 -> 216` approximate tokens
- `4,855 -> 233` approximate tokens
- `9,731 -> 232` approximate tokens
- `6,523 -> 239` approximate tokens

Important: this is not a fixed guarantee per prompt. If the compact pack is not actually smaller than the source context, `codex-agent-mem` skips reinjection instead of pretending it saved tokens.

## What this prevents now

- losing the original objective after a few runs
- silently narrowing scope when the user asked for more
- declaring completion while pending work still exists
- forgetting blockers and re-entering the next run as if the task were finished

## Repository layout

- [src/codex_agent_mem](./src/codex_agent_mem/) - package code
- [tests](./tests/) - executable tests
- [examples/codex](./examples/codex/) - Codex integration examples
- [scripts](./scripts/) - local bootstrap helpers
- [docs](./docs/) - architecture, integration, quickstart, and release notes

## Documentation map

- [AGENTS.md](./AGENTS.md) - repo map and operational guide for coding agents
- [docs/quickstart.md](./docs/quickstart.md) - shortest install and first-run path
- [docs/codex-integration.md](./docs/codex-integration.md) - how notify and MCP fit into Codex
- [docs/verification](./docs/verification/) - reproducible public metrics and v1.0.0 evidence
- [docs/support-matrix.md](./docs/support-matrix.md) - current support and known gaps
- [docs/codex-desktop-lifecycle-note.md](./docs/codex-desktop-lifecycle-note.md) - observed Codex Desktop lifecycle behavior and practical mitigations
- [docs/design-decisions.md](./docs/design-decisions.md) - explicit product and architecture decisions
- [docs/architecture.md](./docs/architecture.md) - narrow technical architecture of the current release
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
