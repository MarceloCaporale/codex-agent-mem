# Verification evidence

This directory contains reproducible, sanitized evidence for codex-agent-mem.

The current v1.0.0 public run was executed with Codex Desktop using GPT-5.4 in a Codex environment, reasoning effort xhigh. This evidence validates the Codex Desktop path; it is not a ChatGPT web/app connector validation.

All verification data is synthetic. The runner uses local SQLite files and local JSON/Markdown outputs only; it does not send memory, prompts, telemetry, or project data to external servers.

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
- `v1.0.0/checksums_sha256.txt`
