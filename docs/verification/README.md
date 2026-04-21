# Verification evidence

This directory contains reproducible, sanitized evidence for codex-agent-mem.

The current v1.0.0 public run was executed with Codex Desktop, model GPT-5.4, reasoning effort xhigh.

The v1.0.0 verification set covers:

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
