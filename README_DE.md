# codex-agent-mem

Weitere Sprachen: [English](./README.md) | [Español](./README_ES.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Portable, local-first Memory-Schicht für Codex und Workflows mit Coding-Agenten.

codex-agent-mem speichert dauerhafte Erkenntnisse aus Agent-Turns in lokalem SQLite, stellt kompakte Abfrage über MCP bereit und hält die Memory-Schicht auditierbar und unter Kontrolle des eigenen Runtimes, statt sie in einem einzelnen Vendor-Runtime zu verstecken.

## Status

`0.2.1` ist die aktuelle öffentliche Basis-Release.

Was heute funktioniert:

- Codex-`notify`-Ingestion bei `agent-turn-complete`
- lokale SQLite-Persistenz mit FTS5
- heuristische Extraktion von `session_summary` und `decision`
- FastAPI-Inspektions-API
- MCP-stdio-Server mit:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
- automatisierte Tests

Was bewusst noch nicht im Scope ist:

- Embeddings
- Vector Stores
- UI
- Codex App Server Ingestion
- Codex-Hooks-Adapter
- Ollama-Adapter
- Multi-Agent-Orchestrierung

## Wichtige Erwartung

Codex installiert aktuell keine beliebigen MCP-Tools direkt in einem Schritt aus einer GitHub-URL.

Der unterstützte Weg ist weiterhin:

1. das Python-Paket installieren
2. Codex-`notify` und `mcp_servers` auf die installierten Kommandos zeigen lassen

Dieses Repository ist so vorbereitet, dass dieser Ablauf sauber und reproduzierbar ist.

## Installation

### Option A: `pipx` von GitHub

Direkt von der Repository-URL installieren:

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### Option B: lokale Entwicklungsinstallation

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

## Codex konfigurieren

Ein sofort einsetzbares Snippet erzeugen:

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Das gibt den `notify`-Block, den Block `[mcp_servers."codex-agent-mem"]` und die Read-only-Freigaben für die MCP-Tools aus, die du in `~/.codex/config.toml` einfügen kannst.

Beispieldateien liegen außerdem unter [examples/codex](./examples/codex/).

## Lokal ausführen

Die Inspektions-API starten:

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Den MCP-Server starten:

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

## Schnelle Verifikation

Den Smoke-Test ausführen:

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Dadurch wird ein Beispiel-Turn eingefügt, Beobachtungen werden extrahiert und die letzte Retrieval-Sicht sowie die `project_brief`-Erzeugung verifiziert.

## Repository-Struktur

- [src/codex_agent_mem](./src/codex_agent_mem/) - Paketcode
- [tests](./tests/) - ausführbare Tests
- [examples/codex](./examples/codex/) - Codex-Integrationsbeispiele
- [scripts](./scripts/) - lokale Bootstrap-Helfer
- [docs](./docs/) - Architektur und Release-Hinweise

## Release-Oberfläche

Dieses Repository enthält:

- sauberes Root-Layout
- installierbares `pyproject.toml`
- Kommando-Entry-Points
- Tests
- CI-Workflow
- Lizenz
- Changelog
