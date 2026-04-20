# v1.0 Roadmap

## Focus

`v1.0` is not about adding more memory features first.

It is about making `codex-agent-mem` more efficient, more observable, and cheaper to run under real host pressure.

The next major slice is:

**observability + low-impact runtime + more efficient continuity selection**

## Why this is the right next step

`v0.6` through `v0.9` already established:

- deterministic closure control
- compact continuity packs
- provenance, health, and snapshots
- governed policies, inheritance, and repairs
- stdio runtime hardening

The next bottleneck is different:

- long-lived hosts can behave badly
- stdio MCP means one process per host connection is normal
- repeated initialization still costs too much when the host opens or retains more connections than it should
- runtime efficiency now matters as much as memory quality

So `v1.0` should prioritize lifecycle cost and runtime evidence before adding broader feature surface.

## v1.0 goals

`v1.0` should make it possible to say:

- this process started for a known reason
- this much work was actually done
- this much context was saved
- this host behavior is normal or abnormal
- this runtime path is low-impact when memory is only being read

## Implementation order

### 1. Runtime observability first

Add stronger local runtime evidence before changing transport architecture.

Deliverables:

- aggregated runtime telemetry
- per-process lifecycle events
- local JSONL event stream
- better runtime summaries in `mem_health_runtime`
- explicit `spawn_storm_warning` signal when too many equivalent MCP processes appear for the same `db_path`

Why first:

- it turns suspicion into evidence
- it makes later daemon work measurable
- it helps distinguish healthy one-process-per-connection behavior from host leakage

### 2. Low-impact runtime modes

Add modes that reduce cost even if the host opens more processes than expected.

Deliverables:

- read-only runtime mode for retrieval-only use
- tool-surface profiles such as:
  - `minimal`
  - `standard`
  - `full`
- smaller default profile for Codex Desktop
- explicit documentation of which tools mutate state and which do not

Why second:

- most retrieval calls do not need write capability
- fewer exposed tools means lower handshake and maintenance cost
- it reduces contention before any daemon architecture exists

### 3. Lazy initialization

Do not fully initialize heavy runtime state until a tool actually needs it.

Deliverables:

- delayed store initialization where possible
- delayed optional subsystems
- “almost free” startup for unused MCP connections

Why third:

- many host connections may initialize MCP and never call it
- that should not cost a full store bootstrap

### 4. Short per-process cache

Avoid rebuilding the same continuity answer repeatedly inside one short-lived process.

Good targets:

- `mem_context_pack`
- `mem_project_brief`
- `mem_open_work`
- `mem_scope_guard`

Cache key ideas:

- `project_key`
- `budget`
- `db_last_modified`
- optional policy fingerprint

Cache lifetime:

- short only, such as `5` to `30` seconds

Why fourth:

- it removes pointless recomputation during retries or repeated handshakes
- it stays safe because invalidation can be conservative

### 5. Optional daemon architecture

Only after instrumentation and low-impact modes are in place, add the larger transport improvement.

Goal:

- one heavier local daemon per user or database
- stdio bridge stays lightweight
- repeated host connections no longer imply repeated heavy initialization

Deliverables:

- optional daemon mode
- lightweight stdio bridge or client
- documented fallback to plain stdio

Why fifth instead of first:

- it is the biggest architectural change
- it is easier to justify once real telemetry proves where the cost is
- it avoids overcorrecting before the runtime is measured

## Concrete deliverables

### Runtime telemetry

- local `events.jsonl` or equivalent
- start / initialize / tool-call / idle-timeout / signal / stdin-eof / exit events
- no cloud dependency

### Runtime health

Extend `mem_health_runtime` with fields such as:

- `spawn_storm_warning`
- `same_db_process_count`
- `profile`
- `read_only`
- `lazy_initialized`
- `cache_hits`
- `cache_misses`

### Low-impact profiles

Suggested first profile split:

- `minimal`
  - `mem_search`
  - `mem_context_pack`
  - `mem_open_work`
  - `mem_completion_check`
  - `mem_health_runtime`
- `standard`
  - current core retrieval set
- `full`
  - current full surface including audit and governance tools

### Read-only fast mode

The MCP process should be able to declare:

- this process can answer queries
- this process will not mutate stored memory

That reduces SQLite write contention and makes lifecycle reasoning cleaner.

## Non-goals for this slice

Not first in `v1.0`:

- embeddings as a default requirement
- vector store as baseline
- broader multi-agent orchestration
- UI redesign as a primary goal

Those may still happen later, but they are not what most improves efficiency right now.

## Acceptance criteria

`v1.0` should be considered successful when:

1. runtime events are observable locally without external infrastructure
2. `mem_health_runtime` can distinguish normal reuse from likely spawn storms
3. retrieval-only use can run in a clearly documented lower-impact mode
4. repeated short-lived calls avoid redundant pack rebuilding through safe short caching
5. the daemon path exists as an option, not as a breaking requirement
6. the repository can explain these behaviors clearly to both humans and other agents

## Product framing after `v1.0`

The product framing stays the same, but gets sharper:

**operational continuity + deterministic closure control + auditable compact reinjection + governed memory selection + observable low-impact runtime behavior**

That is the right direction if the goal is not only “more memory”, but memory that stays cheap, explainable, and resilient under real Codex use.
