# Verification evidence

This directory contains reproducible, sanitized evidence for codex-agent-mem.

The current public run uses synthetic fixtures and records local runtime metadata for the `1.0.x` release line. It is not an external model benchmark.

The verification set covers:

- context compression and token savings;
- repeated-pack avoidance with `known_pack_hash`;
- lazy MCP initialization;
- minimal tool surface;
- read-only safety;
- response diet;
- local telemetry;
- closure-control checks;
- a sub-agent handoff scenario.

Start here:

- `v1.0.0/RESULTS.md`
- `v1.0.0/results.json`
- `v1.0.0/METHODOLOGY.md`
- `v1.0.1/release-gate-summary.md`
- `v1.0.1/writable-defaults-v1.0.1.md`
- `v1.0.1/manual-notes-v1.0.1.md`
- `v1.0.1/checksums_sha256.txt`
