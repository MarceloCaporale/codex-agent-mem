# v1.0.x verification results

These are reproducible, sanitized results generated from synthetic fixtures.

Execution context:

- Runtime: Codex Desktop
- Model: not part of benchmark; synthetic fixtures only
- Reasoning effort: not part of benchmark; synthetic fixtures only

## Snapshot

| Scenario | Source tokens | Pack tokens | Saved | not_modified | Tools | Lazy init | Read-only |
|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | 1,841 | 253 | 86.26% | true | 4 | false->true | true |
| Medium agent workflow | 4,855 | 270 | 94.44% | true | 4 | false->true | true |
| Large repeated audit | 9,731 | 269 | 97.24% | true | 4 | false->true | true |
| Sub-agent handoff example | 6,523 | 276 | 95.77% | true | 4 | false->true | true |

## Token savings by scenario

### Small project continuity

A short project where the agent should remember objective, constraints and open work without repeating the whole discussion.

- Source context: ~1,841 tokens
- Memory pack: ~253 tokens
- Tokens not resent: ~1,588
- Estimated savings: 86.26%
- Pack hash: `700b30ab9323f77d7c8366ebe09bcb7084645bbc31dcf7092fae5a15ca568b48`

`source` [############################] 100.00%
`pack`   [####........................] 13.74%
`saved`  [########################....] 86.26%

### Medium agent workflow

A realistic multi-step implementation with repeated decisions, pending work and DoD requirements.

- Source context: ~4,855 tokens
- Memory pack: ~270 tokens
- Tokens not resent: ~4,585
- Estimated savings: 94.44%
- Pack hash: `b5c6ecd9ec15c6463cbfd924247bba500dca7bbb3834144afc6f7a7051d00aac`

`source` [############################] 100.00%
`pack`   [##..........................] 5.56%
`saved`  [##########################..] 94.44%

### Large repeated audit

A long audit where the same constraints and decisions would normally be re-sent many times.

- Source context: ~9,731 tokens
- Memory pack: ~269 tokens
- Tokens not resent: ~9,462
- Estimated savings: 97.24%
- Pack hash: `6cc762e877b54779ac835bf0820712bbd3e4971472926a3cba110557221e6664`

`source` [############################] 100.00%
`pack`   [#...........................] 2.76%
`saved`  [###########################.] 97.24%

### Sub-agent handoff example

A project where an explorer sub-agent audits context and a worker sub-agent implements a bounded change.

- Source context: ~6,523 tokens
- Memory pack: ~276 tokens
- Tokens not resent: ~6,247
- Estimated savings: 95.77%
- Pack hash: `1e445aab0917fb3baef42a14ad8443e4f94b5758b84601fde013f07ae7b879e8`

`source` [############################] 100.00%
`pack`   [#...........................] 4.23%
`saved`  [###########################.] 95.77%

Sub-agent example:

- `explorer`: Audit the memory surface and identify which facts must never be dropped.
- `worker`: Implement the bounded runtime-efficiency patch without touching documentation.

## Repeated context avoided

`known_pack_hash` lets the agent ask whether a pack changed before re-sending it.

| Scenario | Result |
|---|---|
| Small project continuity | `not_modified=true` |
| Medium agent workflow | `not_modified=true` |
| Large repeated audit | `not_modified=true` |
| Sub-agent handoff example | `not_modified=true` |

## Runtime safety

| Metric | Result |
|---|---|
| Minimal profile tools | mem_open_work, mem_completion_check, mem_context_pack, mem_health_runtime |
| Tool count in minimal profile | 4 |
| Lazy initialization before DB-backed tool | `false` |
| Lazy initialization after context pack | `true` |
| Mutating tool tested in read-only mode | `mem_snapshot_create` |
| Mutating tool blocked | `true` |

This is the v1.0.0 fixture baseline. In v1.0.1, the `minimal` profile also
includes `mem_session_list`, `mem_scope_resolve`, and `mem_bootstrap_context`
so broad workspaces can resolve scope before loading active context.

## Response diet

Text shown to the model can be kept compact while the structured payload remains available to MCP clients.

| Scenario | Compact text chars | Balanced text chars | Verbose text chars |
|---|---:|---:|---:|
| Small project continuity | 160 | 209 | 20,715 |
| Medium agent workflow | 160 | 209 | 42,943 |
| Large repeated audit | 160 | 209 | 76,114 |
| Sub-agent handoff example | 160 | 209 | 54,625 |

## Telemetry smoke

- Telemetry mode tested: `summary`
- Events captured: process_start, initialize, tools_list, tool_call, stdin_eof, process_exit
- Stores memory content: `false`

## Interpretation

These numbers are not a universal guarantee. They show reproducible behavior on public synthetic fixtures.
The expected value is highest when an agent would otherwise resend repeated project context across sessions.
