# Verification methodology

These results are reproducible evidence for codex-agent-mem v1.0.0.

## Execution environment

- Runtime: Codex Desktop
- Model: GPT-5.4
- Reasoning effort: xhigh
- Data: synthetic fixtures only

## What is measured

- Context compression: source tokens vs generated memory pack tokens.
- Repeated-pack avoidance: `known_pack_hash` returning `not_modified=true`.
- Lazy initialization: health/list calls do not initialize SQLite until a DB-backed tool is used.
- Minimal tool surface: the low-impact MCP profile exposes four tools.
- Read-only safety: mutating tools are blocked.
- Response diet: compact, balanced and verbose textual response sizes.
- Telemetry: local JSONL metadata events without memory content.
- Closure control: deterministic refusal to mark work done without evidence.

## Reproducibility

- Fixtures SHA-256: `1e5c295c5b91b4cf9640451d13b645470771f3d068d0aa90b7bbcb964412e36d`
- Runner SHA-256: `6f48ad8b454e53bbf624ba63a6b535066adadc5418f3119c61b7f4f614830972`

Run from the project environment with the public fixture and runner:

```bash
python docs/verification/v1.0.0/run_verification.py --scenario-file docs/verification/v1.0.0/scenarios.json
```

The public result files intentionally avoid private absolute paths and real user data.
