# Verification methodology

These results are reproducible evidence for the codex-agent-mem `1.0.x` public scenario set.

## Execution environment

- Runtime: Codex Desktop
- Model: not part of benchmark; synthetic fixtures only
- Reasoning effort: not part of benchmark; synthetic fixtures only
- Data: synthetic fixtures only

## What is measured

- Context compression: source tokens vs generated memory pack tokens.
- Repeated-pack avoidance: `known_pack_hash` returning `not_modified=true`.
- Lazy initialization: health/list calls do not initialize SQLite until a DB-backed tool is used.
- Minimal tool surface: the v1.0.0 low-impact MCP profile exposes four tools.
  v1.0.1 later adds session/startup scope helpers to `minimal`.
- Read-only safety: mutating tools are blocked.
- Response diet: compact, balanced and verbose textual response sizes.
- Telemetry: local JSONL metadata events without memory content.
- Closure control: deterministic refusal to mark work done without evidence.

## Reproducibility

- Fixtures SHA-256: `1064a3b2e1c74960cd3ae4da13bfb33c949b9f11b805bf58cf9d5c21b719c3ef`
- Runner SHA-256: `7dd20a791cf6df1419ff1cf153d7c2029b690e21e16439621192000dc7ee8816`

Run from the project environment with the public fixture and runner:

```bash
python docs/verification/v1.0.0/run_verification.py --scenario-file docs/verification/v1.0.0/scenarios.json
```

The public result files intentionally avoid private absolute paths and real user data.
