# v1.0.1 Release Gate Summary

Prepared: 2026-05-06

This summary records the v1.0.1 release-gate intent for the public local-first
core. It is a compact index of validation checks; the authoritative asset
hashes are in `checksums_sha256.txt`.

## Retrieval Hygiene No-Regression

| Check | Expected |
| --- | --- |
| `known_pack_hash` repeat | Returns `not_modified=true` for unchanged project/session scope. |
| Compact multi-session pack | Emits a visible scope warning without expanding compact text into the full payload. |
| `max_chars=400` multi-session pack | Keeps the warning inside the compact budget. |
| Search dedupe | Overfetches before dedupe so repeated hits do not hide later unique results. |
| Dominance guard | Uses an expanded candidate pool and preserves protected operational types before final pack truncation. |
| Freshness | Separates last captured turn from last operational capture and states that memory is persisted, not live current-turn awareness. |

## Writable Continuity Gate

| Check | Expected |
| --- | --- |
| Normal MCP mutability | Release smoke starts MCP with `read_only=false`; `--read-only` remains an explicit retrieval-only audit/debug mode. |
| Manual operational memory | `mem_note_create(project_key, text, session_id)` creates a `manual_note` observation. |
| Search retrieval | `mem_search` finds the manual note by exact phrase. |
| Context-pack reuse | `mem_context_pack` includes the manual note for the same project/session scope. |
| Later process continuity | A later MCP subprocess over the same temporary SQLite database finds the same manual note through `mem_search` and `mem_context_pack`, then returns `not_modified=true` for `known_pack_hash`. |
| Snapshot provenance | `mem_snapshot_create(project_key, label, session_id)` stores high-confidence session provenance, and `mem_snapshot_list` exposes it. |

## Artifact Gate

The release gate must rebuild wheel and sdist in an isolated temporary build
directory, smoke the wheel, verify checksums, and export the verified assets to
`.release/v1.0.1`. The exported assets are the only files intended for the
GitHub Release when publication is approved.

Any source, README, docs, tests, metadata, wheel, or sdist change invalidates
the current checksums and requires rerunning the full release gate.
