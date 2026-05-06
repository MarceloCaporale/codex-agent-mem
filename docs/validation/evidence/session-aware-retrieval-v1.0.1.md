# Session-Aware Retrieval Evidence - v1.0.1

Evidence level: L3-R retrieval plus L1 fixtures.

Scope: persisted local memory retrieval. This validation does not claim live
current-turn awareness.

## Fixture Matrix

| Case | Expected | Result |
| --- | --- | --- |
| `mem_session_list(project_key)` | Lists recent persisted sessions as object-root `{items, count}` | PASS |
| `mem_scope_resolve(project_key)` without hint | Returns candidate lanes but no `recommended_scope` and no arbitrary first-lane selection | PASS |
| `mem_bootstrap_context(project_key)` without hint in multi-lane project | Returns `context_pack=null` and `do_not_fetch_project_wide_pack=true` | PASS |
| `mem_bootstrap_context(project_key, thread_hint=...)` with matching lane/session evidence | Returns `lane_needs_session_selection`, `context_pack=null`, and candidate lanes instead of auto-selecting a session | PASS |
| `mem_bootstrap_context(project_key, session_id=N)` with explicit session id | Returns a session-scoped pack with `session_filter_applied=true` | PASS |
| `mem_context_pack(project_key)` without `session_id` | `session_filter_applied=false`, `source_session_count > 1` for broad scopes | PASS |
| Broad global pack spanning multiple sessions/sub-scopes | Visible `scope_warning=multi_session_project_scope` in stats, compact text, and pack text | PASS |
| Broad global pack objective | Marked as `Objective (project-wide candidate)` instead of active-thread certainty | PASS |
| `mem_context_pack(project_key, session_id=A)` | `session_filter_applied=true`, `source_session_count=1` | PASS |
| `mem_search(query from B, session_id=A)` | No results from the other session | PASS |
| `mem_search(project_key)` global results | Include project/session IDs, external session, cwd, retrieval scope, and capture timestamp | PASS |
| `mem_open_work(project_key, session_id=A)` | Does not mix pending items from B | PASS |
| `project_key=A`, `session_id` from B | Clear fail-closed error | PASS |
| `known_pack_hash` with same project/session scope | Returns `not_modified=true` on repeat call | PASS |
| `known_pack_hash` after volatile age changes | Still returns `not_modified=true` because `memory_age_seconds` is excluded from the hash | PASS |
| `known_pack_hash` from a different scope | Does not hide the scoped pack | PASS |
| Internal/title-generation prompt session | Marked low-value and not used as the operational session label | PASS |
| Internal prompt followed by operational turn | Session label uses the later operational turn instead of fallback/title noise | PASS |
| Repeated retrieval observations | Collapsed with duplicate counts instead of repeated pack/search noise | PASS |
| Same text with different type/status | Preserved as distinct operational memory; only same type/status/text duplicates collapse | PASS |
| Search dedupe under many repeated hits | Overfetches before dedupe so duplicates do not hide later unique results | PASS |
| Large session in a global pack | Per-session dominance cap prevents one session from taking over the pack | PASS |
| Large session before smaller relevant session | Expanded candidate pool keeps smaller-session evidence visible before final pack cut | PASS |
| Protected operational item under cap | Blockers, pending items, DoD gaps, constraints, objectives, and completion claims survive mechanical caps | PASS |
| Freshness with recent internal prompt | Reports last operational capture separately from last captured turn | PASS |
| Session metadata version provenance | Reported as session-scoped metadata, not exact per-observation capture certainty | PASS |
| `mem_session_list(query=...)` / `sub_scope_hint` | Narrows recent sessions by display label, path/sub-scope hints, previews, cwd, and external session id | PASS |
| Session metadata upsert | Merges existing metadata with new version markers instead of clobbering prior model/source fields | PASS |
| Notify/API project identity from broad cwd | Uses referenced repository path, AGENTS scope, or project-state canonical name instead of persisting broad/technical cwd as the project key | PASS |

## Tool Coverage

| Tool | Historical behavior without `session_id` | Filters with `session_id` | Project/session mismatch fails closed | Covered by tests |
| --- | ---: | ---: | ---: | ---: |
| `mem_context_pack` | PASS | PASS | PASS | PASS |
| `mem_scope_resolve` | PASS | N/A | PASS | PASS |
| `mem_bootstrap_context` | PASS | PASS | PASS | PASS |
| `mem_search` | PASS | PASS | PASS | PASS |
| `mem_recent` | PASS | PASS | PASS | PASS |
| `mem_project_brief` | PASS | PASS | PASS | PASS |
| `mem_open_work` | PASS | PASS | PASS | PASS |
| `mem_completion_check` | PASS | PASS | PASS | PASS |
| `mem_scope_guard` | PASS | PASS | PASS | PASS |
| `mem_recent_changes` | PASS | PASS | PASS | PASS |

## Pack Hash Scope

| Case | Expected | Result |
| --- | --- | --- |
| Global pack hash | Present | PASS |
| Session A pack hash | Present | PASS |
| Global hash differs from scoped hash | True when scope metadata/content differs | PASS |
| Session A repeat call with same `known_pack_hash` | `not_modified=true` | PASS |
| Session A repeat after `memory_age_seconds` changes | `not_modified=true`; volatile age is not part of the stable hash | PASS |
| Session A repeat after `operational_memory_age_seconds` changes | `not_modified=true`; volatile operational age is not part of the stable hash | PASS |
| Global hash reused as scoped `known_pack_hash` | Does not return false `not_modified` | PASS |

## Response Diet No-Regression

The post-hardening fixture keeps the response-diet contract intact:

| Case | Expected | Result |
| --- | --- | --- |
| Multi-session pack with `max_chars=400` | Visible scope warning stays inside the requested compact budget | PASS |
| Compact `content.text` | Shows only scope breadcrumbs, source-session count, freshness cue, and narrowing hint | PASS |
| Full details | Remain in object-root `structuredContent` for clients that expose structured payloads | PASS |
| Repeated unchanged pack | Uses `known_pack_hash` / `not_modified=true` instead of resending the pack | PASS |
| Token-savings claim | Remains tied to documented synthetic fixtures, not a universal guarantee | PASS |

## Client Visibility

| Client/runtime | Response mode | Structured payload visible | Session hint visibility | Result |
| --- | --- | ---: | ---: | --- |
| Codex | `compact` | Yes | Yes | PASS |
| Google Gemini CLI | `verbose` | Yes, JSON visible | Yes | PASS |
| Claude Code | `compact` | Yes | Via `structuredContent.stats`; raw `content[0].text` breadcrumbs were verified at daemon level but not surfaced in Claude Code's model-visible summary | PASS |
| MCP subprocess smoke | `compact` | Yes | Yes | PASS |

## Broad-Scope Stress Case

The v1.0.1 stress fixture models a broad `project_key` containing multiple
persisted sessions and inferred sub-scopes. Defensive startup now begins with
`mem_bootstrap_context`: without an explicit `session_id` it returns candidate
lanes and does not fetch a project-wide pack; with an explicit persisted
session id it returns a scoped pack. A direct global context pack remains available for broad
continuity, but it emits a visible scope warning, reports persisted-memory
freshness, marks the objective as a project-wide candidate, and recommends
narrowing before a client treats the pack as active-thread continuity.

## Release Gate

Session-aware retrieval is covered by the v1.0.1 pytest suite and MCP contract
smoke. Final release assets must be regenerated after any source or versioned
documentation change, because documentation files enter the sdist.
