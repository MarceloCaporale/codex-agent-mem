# Snapshot Provenance Verification - v1.0.1

Date: 2026-04-29

## Scope

This verification covers the v1.0.1 snapshot provenance fix for broad project
scopes such as `multi-project-workspace`, where one `project_key` can contain
multiple real projects, subprojects, or client/runtime sessions.

## Contract

- `mem_snapshot_create(project_key, label, session_id?)` accepts an optional
  internal MCP `session_id`.
- When `session_id` is provided, it is validated against `project_key`.
- When `session_id` is omitted, the snapshot is not attached to the latest
  project turn.
- Unscoped snapshots are recorded with `provenance_confidence=low` and a
  provenance warning.
- `mem_snapshot_list(project_key)` exposes audit fields:
  `snapshot_id`, `project_key`, `label`, `session_id`, `external_session_id`,
  `cwd`, `project_root_path`, `display_label`, `provenance_confidence`,
  `provenance_warning`, and `created_at`.

## Files Changed

- `src/codex_agent_mem/db.py`
- `src/codex_agent_mem/mcp_stdio.py`
- `tests/test_session_aware_retrieval.py`
- `tests/test_mcp.py`
- `RELEASE_NOTES_v1.0.1.md`
- `CHANGELOG.md`

## Verification

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_session_aware_retrieval.py tests\test_mcp.py
```

Result:

```text
21 passed in 2.22s
```

Full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Result:

```text
75 passed in 6.32s
```

## Result

PASS.

The worktree no longer creates high-confidence snapshot provenance from the
latest project turn when no `session_id` is supplied. Explicit `session_id`
snapshots are session-filtered, listable with provenance fields, and reject
session IDs from other projects.
