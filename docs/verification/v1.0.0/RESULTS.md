# v1.0.0 verification results

These are reproducible, sanitized results generated from synthetic fixtures.

Execution context:

- Runtime: Codex Desktop in a Codex environment
- Model: GPT-5.4
- Reasoning effort: xhigh

Scope: this validates Codex Desktop, not a ChatGPT web/app connector. Claude web / claude.ai support is also not inferred from these results.

## Snapshot

| Scenario | Source tokens | Pack tokens | Saved | not_modified | Tools | Lazy init | Read-only |
|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | 1,841 | 216 | 88.27% | true | 4 | false->true | true |
| Medium agent workflow | 4,855 | 233 | 95.20% | true | 4 | false->true | true |
| Large repeated audit | 9,731 | 232 | 97.62% | true | 4 | false->true | true |
| Sub-agent handoff example | 6,523 | 239 | 96.34% | true | 4 | false->true | true |

Across these fixtures: ~22,950 source tokens -> ~920 pack tokens.
Approximate repeated-context reduction: 95.99% (~22,030 tokens not resent).

## Token savings by scenario

### Small project continuity

A short project where the agent should remember objective, constraints and open work without repeating the whole discussion.

- Source context: ~1,841 tokens
- Memory pack: ~216 tokens
- Tokens not resent: ~1,625
- Estimated savings: 88.27%
- Pack hash: `9c219f1ea5993da6389c683a029e57c40aed129186e9fdfbe9de8058845967d7`

`source` [############################] 100.00%
`pack`   [###.........................] 11.73%
`saved`  [#########################...] 88.27%

### Medium agent workflow

A realistic multi-step implementation with repeated decisions, pending work and DoD requirements.

- Source context: ~4,855 tokens
- Memory pack: ~233 tokens
- Tokens not resent: ~4,622
- Estimated savings: 95.20%
- Pack hash: `762cd3a6bb36f47b76bf12f629b55e2c9d4c18b7e59a3a94083af580c012775b`

`source` [############################] 100.00%
`pack`   [#...........................] 4.80%
`saved`  [###########################.] 95.20%

### Large repeated audit

A long audit where the same constraints and decisions would normally be re-sent many times.

- Source context: ~9,731 tokens
- Memory pack: ~232 tokens
- Tokens not resent: ~9,499
- Estimated savings: 97.62%
- Pack hash: `2a4983655139737e718c1a4315e1797a805eeb5294eba9e8dd5cb8472bcbad50`

`source` [############################] 100.00%
`pack`   [#...........................] 2.38%
`saved`  [###########################.] 97.62%

### Sub-agent handoff example

A project where an explorer sub-agent audits context and a worker sub-agent implements a bounded change.

- Source context: ~6,523 tokens
- Memory pack: ~239 tokens
- Tokens not resent: ~6,284
- Estimated savings: 96.34%
- Pack hash: `55cfc4345a1ccafeb426c30e451a13fa8da84e928a501b165d8e82d5be7c4e46`

`source` [############################] 100.00%
`pack`   [#...........................] 3.66%
`saved`  [###########################.] 96.34%

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

## Response diet

Text shown to the model can be kept compact while the structured payload remains available to MCP clients.

| Scenario | Compact text chars | Balanced text chars | Verbose text chars |
|---|---:|---:|---:|
| Small project continuity | 160 | 209 | 20,565 |
| Medium agent workflow | 160 | 209 | 42,793 |
| Large repeated audit | 160 | 209 | 75,965 |
| Sub-agent handoff example | 160 | 209 | 54,476 |

## Telemetry smoke

- Telemetry mode tested: `summary`
- Events captured: process_start, initialize, tools_list, tool_call, stdin_eof, process_exit
- Stores memory content: `false`

## Interpretation

These numbers are not a universal guarantee. They show reproducible behavior on public synthetic fixtures.
The expected value is highest when an agent would otherwise resend repeated project context across sessions.
