# Release Notes v1.0.2

Released: 2026-05-07

`codex-agent-mem` v1.0.2 is a focused identity/scope hardening patch for the
public 1.0.x line.

## Fixed

- Fixed a project identity edge case where generated `codex-agent-mem` context
  inside `AGENTS.md` could be mistaken for the active project scope.
- Preserved existing project `root_path` metadata when a later conflicting
  project update is observed.
- Allowed `mem_note_create` to initialize a missing local project record before
  storing the first manual note.

## Scope

This patch does not add hosted services, cloud sync, OAuth, external memory
servers, or v1.8-only roadmap capabilities. It keeps the public 1.0.x line
local-first, SQLite-backed, auditable, and MCP-compatible.

## Validation

The release gate for v1.0.2 should include:

- `pytest`
- `ruff`
- `compileall`
- MCP contract smoke, in-process and subprocess
- repository hygiene checks
- isolated release build and wheel smoke
- final release checksum verification
