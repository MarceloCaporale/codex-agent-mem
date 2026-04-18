# Security Policy

## Supported versions

| Version line | Status |
| --- | --- |
| `0.4.x` | Supported |
| `< 0.4.0` | Not supported |

## Scope

Security reports are most relevant for:

- local SQLite persistence
- FastAPI inspection API
- local inspection UI
- generated AGENTS.md working-memory sync
- MCP stdio surface
- Codex notify ingestion
- packaging and install workflow

## Reporting a vulnerability

Please avoid posting exploit details in a public issue.

Preferred path:

1. Use GitHub Security Advisories for this repository, if enabled.
2. If advisories are not enabled, contact the maintainer privately through GitHub.
3. If neither path is available, open a minimal public issue without exploit details and request a private follow-up channel.

## What to include

- affected version or commit
- operating system
- exact entry point or command involved
- reproduction steps
- impact description
- whether the issue is local-only or remotely triggerable

## Response expectations

This is an early public release line. The project aims to respond pragmatically and quickly, but no formal SLA is promised yet.
