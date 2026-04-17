# Support Matrix

## Runtime and platform support

| Area | Status | Notes |
| --- | --- | --- |
| Windows local development | Supported | Primary practical target today |
| Linux CI | Supported | Covered in GitHub Actions |
| Windows CI | Supported | Covered in GitHub Actions |
| macOS local development | Expected but not verified | No CI coverage yet |
| Codex notify capture | Supported | Current primary capture path |
| MCP stdio retrieval | Supported | Current primary retrieval path |
| FastAPI inspection API | Supported | Local inspection surface |
| Optional HTTP notify wrapper | Supported | Secondary path only |
| Codex hooks adapter | Not yet supported | Deferred |
| Codex App Server ingestion | Not yet supported | Deferred |
| Ollama adapter | Not yet supported | Deferred |
| Vector search / embeddings | Not yet supported | Deferred |
| UI | Not yet supported | Deferred |

## Version support

| Component | Current expectation |
| --- | --- |
| Python | 3.12+ |
| SQLite | Local system SQLite with FTS5 support preferred |
| Codex integration model | `notify` + MCP config |
