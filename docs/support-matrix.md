# Support Matrix

## Runtime and platform support

| Area | Status | Notes |
| --- | --- | --- |
| Windows local development | Supported | Primary practical target today |
| Linux CI | Supported | Covered in GitHub Actions |
| Windows CI | Supported | Covered in GitHub Actions |
| macOS local development | Expected but not verified | No CI coverage yet |
| Codex notify capture | Supported | Current primary capture path |
| AGENTS-based continuity reinjection | Supported | Enabled through `--sync-project-doc` when the generated pack is smaller than source context |
| Operational-state carry-forward | Supported | Objective, pending work, blockers, and guardrails are derived and injected into the working-memory pack |
| False-completion guardrails | Supported | The generated pack explicitly tells Codex not to declare completion while pending work remains |
| MCP stdio retrieval | Supported | Current primary retrieval path |
| `mem_context_pack` compact retrieval | Supported | Returns the compressed continuity pack and approximate token budget |
| `mem_context_pack` auto budget | Supported | Selects the smallest fitting budget profile from `micro`, `normal`, and `full` |
| `mem_recent_changes` delta retrieval | Supported | Summarizes what changed since the last meaningful continuity baseline |
| `mem_scope_guard` continuity guard | Supported | Exposes must-not-drop scope, active constraints, and closure conflicts |
| FastAPI inspection API | Supported | Local inspection surface |
| Context sync metrics | Supported | Pack sync/skip events are stored per project and exposed through API/UI |
| Optional HTTP notify wrapper | Supported | Secondary path only |
| Codex hooks adapter | Not yet supported | Deferred |
| Codex App Server ingestion | Not yet supported | Deferred |
| Ollama adapter | Not yet supported | Deferred |
| Vector search / embeddings | Not yet supported | Deferred |
| Local inspection UI | Supported | Served by FastAPI at `/ui`, including recent changes, scope guard, closure, and sync metrics |

## Version support

| Component | Current expectation |
| --- | --- |
| Python | 3.12+ |
| SQLite | Local system SQLite with FTS5 support preferred |
| Codex integration model | `notify` + MCP config |
