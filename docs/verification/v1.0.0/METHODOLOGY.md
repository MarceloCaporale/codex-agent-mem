# Verification methodology

These results are reproducible evidence for codex-agent-mem v1.0.0.

## Execution environment

- Runtime: Codex Desktop in a Codex environment
- Model: GPT-5.4
- Reasoning effort: xhigh
- Data: synthetic fixtures only
- Network / privacy: local files and local SQLite only; no memory, prompts, telemetry, or project data are sent to external servers by this runner

This methodology validates the Codex Desktop path. It does not validate a ChatGPT web/app connector, and it should not be used as evidence for Claude web / claude.ai support.

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

- Fixtures SHA-256: `2e7e4dacf44727ae9b6181fb488c4ce062ba37af9c23e212ded4bab9b6105149`
- Runner SHA-256: `e1fc6244f71b731d3ee7c88f86f1a02c10bcad53d9b9d66399d3809543d1ccb0`

Run from the project environment with the public fixture and runner:

```bash
python docs/verification/v1.0.0/run_verification.py --scenario-file docs/verification/v1.0.0/scenarios.json
```

The public result files intentionally avoid private absolute paths and real user data.
