# v1.0 Roadmap

## Focus

`v1.0` is the release where `codex-agent-mem` becomes not just a correct MCP with strong memory features, but a **low-impact continuity runtime** that stays useful even when the host lifecycle is noisy or imperfect.

The priority is no longer “more memory surface first”.

The priority is:

**lower process cost + lower response cost + less repeated continuity transfer**

## Why `v1.0` is different

`v0.6` through `v0.9` already established:

- deterministic closure control
- compact continuity packs
- provenance, health, and snapshots
- governed policies, inheritance, and repairs
- stdio runtime hardening

That means the next problem is not feature absence. It is **efficiency under real usage**:

- long-lived hosts can retain more MCP processes than they should
- stdio naturally means one process per host connection
- repeated startup cost matters when lifecycle noise grows
- large or duplicated tool responses waste exactly the tokens this project is meant to save
- unchanged continuity should not be rebuilt and resent repeatedly

## Product goal for `v1.0`

By the end of `v1.0`, `codex-agent-mem` should be able to say:

- retrieval can run in a clearly lower-impact mode
- unused MCP connections cost very little
- tool responses are compact by default and expand only on demand
- repeated short-lived calls avoid redundant work
- unchanged continuity packs can be reused instead of resent
- runtime degradation is easier to detect and explain
- daemonized reuse exists as an option, not a hidden requirement

## Guiding principle

The implementation order matters.

`v1.0` should follow this rule:

**reduce cost first, initialize late, send less, rebuild less, observe better, daemonize last**

The daemon remains the structural north star, but it should not be the first implementation step.

## What `v1.0` is optimizing

`v1.0` explicitly optimizes three different costs:

1. **process cost**
2. **response cost**
3. **continuity reuse cost**

The roadmap should be evaluated against those three axes, not only against feature count.

## Implementation order

### 1. Low-impact runtime mode

This is the first priority.

Before adding more instrumentation, the MCP should become cheaper to run under noisy host behavior.

#### Deliverables

- explicit `--read-only` mode for retrieval-only runtime
- explicit tool-surface profiles:
  - `minimal`
  - `standard`
  - `full`
- bootstrap support so Codex Desktop can default to a smaller profile
- runtime self-reporting of the active profile and mutability mode

#### Minimal profile target

The first `minimal` profile should stay continuity-first and low-noise:

- `mem_context_pack`
- `mem_open_work`
- `mem_completion_check`
- `mem_health_runtime`

`mem_search` should move to `standard` unless it can be made similarly cheap by default.

#### Why this comes first

- fewer tools means less handshake and lifecycle overhead
- real `read-only` mode reduces write contention
- this lowers cost even if the host still opens too many stdio connections

### 2. Response diet and compact MCP outputs

Once the runtime surface is smaller, the next waste to remove is oversized tool output.

#### Deliverables

- compact-by-default MCP responses
- `content.text` becomes a compact capsule rather than full pretty JSON
- full structured data stays in `structuredContent` when supported
- explicit response modes:
  - `compact`
  - `balanced`
  - `verbose`
- common narrowing arguments where appropriate:
  - `detail`
  - `max_items`
  - `max_chars`
  - `include_provenance`

#### Design rule

The runtime should not send the same payload twice in two verbose forms.

#### Why this comes second

- response tokens are part of the product cost
- reducing output size can save tokens immediately without changing memory semantics

### 3. Lazy initialization

Once the process surface and response size are smaller, the next priority is startup cost.

#### Deliverables

- defer store-heavy initialization until the first tool that really needs it
- avoid initializing optional subsystems for profiles that never use them
- make a connection that starts and exits without useful work almost free

#### Why this comes third

- many hosts initialize MCPs optimistically
- a connection that is never used meaningfully should not pay the full runtime cost

### 4. Revision-stamped short cache

After startup cost is reduced, the next waste to remove is short-window recomputation.

#### Initial cache targets

- `mem_context_pack`
- `mem_project_brief`
- `mem_open_work`
- `mem_scope_guard`

#### Cache key ideas

- `project_key`
- `project_revision`
- `budget`
- optional policy fingerprint
- optional inheritance fingerprint

#### Cache lifetime

Short only:

- `5` to `30` seconds

#### Why this comes fourth

- retries and repeated handshakes can ask the same question several times in a row
- caching against a project revision is more reliable than file mtime for SQLite-based state

### 5. Continuity pack hash and not-modified protocol

After short-window recomputation is reduced, the next gain is reusing continuity when it has not changed.

#### Deliverables

- `known_pack_hash` support for `mem_context_pack`
- `not_modified=true` responses when continuity is unchanged
- a stable compact spine for continuity:
  - objective
  - hard constraints
  - open work
  - blockers
  - DoD gaps
  - critical decisions
  - memory IDs or references

#### Why this matters

- unchanged continuity should not be resent just because the host asks again
- this saves tokens without reducing precision

### 6. Runtime warning and health enrichment

Once the runtime is already cheaper and quieter, expand observability in the most immediately useful places.

#### Deliverables

Extend `mem_health_runtime` with:

- `spawn_storm_warning`
- `same_db_process_count`
- `profile`
- `read_only`
- `lazy_initialized`
- `cache_hits`
- `cache_misses`
- `last_request_ts`

#### Why this is phase six

- by this point the runtime is already cheaper
- diagnostics are then describing a lower-cost system instead of merely documenting an expensive one

### 7. Local runtime telemetry

After the runtime is smaller and health reporting is stronger, add fuller lifecycle evidence.

#### Deliverables

- local JSONL event stream
- per-process lifecycle events such as:
  - `process_start`
  - `initialize`
  - `tool_list`
  - `tool_call`
  - `idle_timeout`
  - `stdin_eof`
  - `signal`
  - `process_exit`
- bounded logging with rotation and size limits

#### Event fields

- `pid`
- `ppid`
- `db_path`
- `project_key` when available
- `profile`
- `read_only`
- `start_ts`
- `event_ts`
- `requests_count`
- `idle_timeout_seconds`
- `exit_reason`

#### Why not earlier

Once the main lifecycle diagnosis is already understood, telemetry is more valuable as operational evidence than as the first engineering move.

### 8. Optional daemon architecture

Only after the runtime is already lower-impact, compact, instrumented, and measured should the project add the bigger transport improvement.

#### Goal

- one heavier daemon per user or per database
- a lightweight stdio bridge in front of it
- cheaper handling of repeated host connections

#### Deliverables

- optional daemon mode
- stdio bridge or thin client
- documented fallback to plain stdio
- runtime evidence showing when daemon mode is actually beneficial

#### Why last

- it is the most invasive architectural change
- it should be justified by measured cost, not only by theory
- stdio remains the honest baseline and should continue to work

## Packaging direction

`v1.0` should also reduce unnecessary install weight where possible.

The preferred direction is:

- keep core MCP/runtime dependencies minimal
- move API/UI dependencies into an optional extra where practical

This is not the first implementation step, but it supports the same low-impact goal.

## Concrete acceptance criteria

`v1.0` should be considered successful when all of the following are true:

1. A retrieval-only Codex Desktop configuration can run `codex-agent-mem` in a clearly documented lower-impact mode.
2. A connection that initializes but does not perform meaningful work has noticeably lower startup cost than today.
3. Core tools return materially smaller responses by default without losing critical continuity precision.
4. Repeated short-lived retrieval calls avoid unnecessary recomputation for compact packs and project summaries.
5. `mem_context_pack` can avoid resending unchanged continuity when given a known pack hash.
6. `mem_health_runtime` can distinguish ordinary stdio reuse from likely spawn-storm conditions.
7. Local runtime telemetry exists without adding any cloud dependency.
8. The daemon path exists as an option, not as a forced transport rewrite.

## Non-goals for this slice

The following should not displace the roadmap above:

- embeddings as a baseline requirement
- vector search as the primary retrieval layer
- major UI redesign
- broader multi-agent orchestration
- expanding governance surface further before runtime efficiency work lands

## Final framing

After `v1.0`, the product promise becomes more precise:

**operational continuity + deterministic closure control + auditable compact reinjection + governed memory selection + low-impact, low-noise runtime behavior**

That is the right outcome for a project whose value is not just “remember more”, but “remember what matters while staying cheap, explainable, and resilient in real Codex use.”
