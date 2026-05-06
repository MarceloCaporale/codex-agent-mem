# Security Policy

## Supported versions

| Version line | Status |
| --- | --- |
| `1.0.x` | Supported local-first MCP core |
| `< 1.0.0` | Best-effort only |

## Scope

Security reports are most relevant for:

- local SQLite persistence
- FastAPI inspection API
- local inspection UI
- generated AGENTS.md working-memory sync
- MCP stdio surface
- agent turn ingestion, including Codex notify
- packaging and install workflow

The supported public scope is local-first: local SQLite, local MCP stdio, the optional loopback daemon/stdio bridge, local API/UI, and documented local agent runtime configuration.

## Local data and daemon security

`codex-agent-mem` stores local memory in a plaintext SQLite database by default. Treat that file as sensitive project data. Do not use it as a secrets vault, avoid storing credentials or API keys in prompts or memory, and keep the database under a local user-protected path. Encryption at rest is not part of the public `1.0.x` line.

The optional daemon in `1.0.x` is local-first and loopback-only. It rejects remote bind hosts by default, can require `Authorization: Bearer <token>` for `/mcp`, and exposes only sanitized runtime metadata on `/health`. The bearer token is a local safeguard, not hosted authentication, TLS, OAuth, or a remote access-control layer.

Generated continuity packs include retrieved memory as advisory project context. Current system, developer, and user instructions still override retrieved memory. This is a basic guardrail against instruction confusion, not a guarantee that prompt injection is impossible.

The public `1.0.x` package does not provide hosted authentication, multi-tenant isolation, remote telemetry, or built-in encryption. If you need stronger local protection, place the SQLite database on an encrypted volume or inside an operating-system-protected user profile.

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

The project aims to respond pragmatically and quickly, but no formal SLA is promised.
