# Writable Defaults Verification - v1.0.1

Date: 2026-04-29

## Purpose

Verify that the public v1.0.1 contract treats writable MCP runtime as the normal
continuity mode and keeps `--read-only` as an explicit retrieval-only
audit/debug mode.

## Changes Verified

- Quickstart stdio and daemon examples no longer include `--read-only` by
  default.
- Codex bootstrap keeps `mcp_read_only=False` as the default and no longer names
  the standard tool approval set as read-only.
- The MCP contract smoke now starts the runtime with `read_only=false`.
- The MCP contract smoke calls `mem_note_create(project_key, text, session_id)`
  and verifies that the resulting `manual_note` is recoverable through
  `mem_search` and `mem_context_pack`.
- The MCP contract smoke calls `mem_snapshot_create(project_key, label,
  session_id)` and verifies high-confidence snapshot provenance.
- Existing read-only behavior remains covered by focused tests that verify
  mutating tools are blocked when `--read-only` is explicitly enabled.

## Local Verification

```text
python -m pytest tests/test_bootstrap_codex.py tests/test_session_aware_retrieval.py tests/test_mcp.py tests/test_manual_notes.py
33 passed

python scripts/mcp_contract_smoke.py --both
PASS: MCP contract smoke (in-process)
PASS: MCP contract smoke (subprocess)
```

## Result

PASS.

The default public workflow is writable. `--read-only` remains available for
explicit retrieval-only audit/debug runs and should not be presented as the
normal continuity configuration.
