# Token-Savings Methodology

`codex-agent-mem` is designed to reduce repeated operational context, not to
guarantee fewer tokens for every prompt. Savings appear when an agent would
otherwise resend the same project state, decisions, blockers, and scope rules
across sessions.

## Mechanism

The runtime builds compact continuity packs from stored local memory:

- project objective and active user scope;
- durable decisions;
- constraints and guardrails;
- pending work, blockers, and Definition of Done gaps;
- recent completed work and resumable context.

`mem_context_pack` returns the pack with approximate source and pack token
counts. The result also includes `pack_hash`. A later call can pass
`known_pack_hash`; if the pack is unchanged, the server returns
`not_modified=true` instead of resending the full pack.

Session-aware retrieval also reduces avoidable context in broad workspaces.
`mem_session_list(project_key)` lets an agent choose a persisted session, then
pass `session_id` to retrieval tools. This avoids sending unrelated
sessions into a pack when a LAB, monorepo, or multi-agent workspace shares one
project scope.

## Current public fixture results

The public v1.0.x fixture set is synthetic and reproducible. It does not use
private chats, credentials, or real user project data.

| Scenario | Source tokens | Pack tokens | Estimated reduction | `not_modified` |
| --- | ---: | ---: | ---: | --- |
| Small project continuity | 1,841 | 253 | 86.26% | true |
| Medium agent workflow | 4,855 | 270 | 94.44% | true |
| Large repeated audit | 9,731 | 269 | 97.24% | true |
| Sub-agent handoff example | 6,523 | 276 | 95.77% | true |

Across those fixtures, repeated context was reduced from about 22,950 source
tokens to about 1,068 pack tokens, an approximate 95.35% reduction for that
controlled workload.

See the raw evidence:

- [v1.0.x verification results](../verification/v1.0.0/RESULTS.md)
- [v1.0.x verification methodology](../verification/v1.0.0/METHODOLOGY.md)
- [v1.0.x results JSON](../verification/v1.0.0/results.json)

## What to measure

For a fair sustained-use evaluation, measure more than the first empty call.
Use several real or simulated sessions and make sure there is enough reusable
memory for a pack to matter.

Track:

- source context tokens that would otherwise be pasted or reinjected;
- generated pack tokens;
- compression ratio;
- number and frequency of `not_modified=true` responses;
- how often the agent needs targeted expansion through `mem_search` or other
  tools;
- whether open work, blockers, and scope rules are preserved;
- latency and runtime profile used by the client;
- client response mode and whether the model could read the useful payload.

Compare against a baseline where the same operational context is manually
pasted or reinjected in full. Keep quality of continuity separate from token
count: a smaller pack is useful only when it preserves the context needed for
the next step.

## What not to claim

- Do not claim guaranteed token reduction.
- Do not extrapolate the fixture percentage to every project or prompt.
- Do not count a first call with no reusable memory as a meaningful savings
  benchmark.
- Do not treat `not_modified=true` as proof that the project did not change in
  every possible sense; it means the generated pack for that call did not
  change.
- Do not compare compact `content.text` against verbose `content.text` as if
  that alone measured continuity quality. The complete payload is in
  `structuredContent`.

## Recommended report format

For each sustained-use run, report:

| Field | Description |
| --- | --- |
| Client/runtime | Exact MCP client, model if relevant, and operating system. |
| Profile | `minimal`, `standard`, or `full`. |
| Mutability | Whether `--read-only` was enabled. |
| Response mode | `compact`, `balanced`, or `verbose`. |
| Source tokens | Approximate repeated context tokens avoided. |
| Pack tokens | Approximate generated pack tokens. |
| `pack_hash` reuse | Number of repeated calls and `not_modified=true` rate. |
| Expansion tools | Search/provenance/health calls needed after the pack. |
| Continuity quality | Whether objective, constraints, open work, blockers, and DoD gaps were preserved. |
| Limits | Anything the client hid, summarized, or failed to expose. |
