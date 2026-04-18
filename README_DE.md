# codex-agent-mem

Weitere Sprachen: [English](./README.md) | [Español](./README_ES.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Portable, local-first Memory-Schicht für Codex und Workflows mit Coding-Agenten.

codex-agent-mem speichert dauerhafte Erkenntnisse aus Agent-Turns in lokalem SQLite, stellt kompakte Abfrage über MCP bereit und hält die Memory-Schicht auditierbar und unter Kontrolle des eigenen Runtimes, statt sie in einem einzelnen Vendor-Runtime zu verstecken.

## Status

`0.7.0` ist die aktuelle Basis-Release.

Was heute funktioniert:

- Codex-`notify`-Ingestion bei `agent-turn-complete`
- lokale SQLite-Persistenz mit FTS5
- heuristische Extraktion von `session_summary`, `decision`, `objective`, `constraint`, `pending_item`, `completed_item`, `blocker` und `completion_claim`
- hierarchische Definition of Done über `project_dod`, `mission_dod` und `session_dod`
- generierte kompakte Continuity-Packs mit ungefährer Token-Schätzung
- Budget-Profile für Packs: `micro`, `normal` und `full`
- automatische `AGENTS.md`-Synchronisierung, wenn das Pack wirklich kleiner als der Quellkontext ist
- Weitergabe von Operational State, damit die nächste Session Ziel, offene Punkte, Blocker und Scope-Guardrails wiederherstellen kann
- deterministische Closure-Control mit `mem_open_work` und `mem_completion_check`
- Delta-Sicht auf neue Änderungen über `mem_recent_changes`
- Scope-Continuity und Must-not-drop-Guardrails über `mem_scope_guard`
- Guardrails gegen falsches „fertig“, wenn noch Pending Items, Blocker oder DoD-Lücken offen sind
- persistierte Closure- und Kompressionsmetriken pro Projekt
- automatische Budgetwahl für Context-Packs bei `budget=auto`
- FastAPI-Inspektions-API
- lokale Inspektions-UI unter `/ui`, inklusive Recent Changes und Scope Guard
- MCP-stdio-Server mit:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
  - `mem_open_work`
  - `mem_completion_check`
  - `mem_recent_changes`
  - `mem_scope_guard`
  - `mem_context_pack`
- automatisierte Tests

Was bewusst noch nicht im Scope ist:

- Embeddings
- Vector Stores
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

Danach im Browser öffnen:

```text
http://127.0.0.1:37770/ui
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

## Ungefähre Token-Einsparung

Einfach gesagt: Das Ziel ist, die Menge des wiederholten Kontexts zu verringern, die man Codex erneut geben muss. Es beseitigt diese Wiederholung nicht vollständig, kann sie aber spürbar verkleinern.

Was wir aus lokaler Validierung ehrlich sagen können:

- in günstigen Fällen reduzierte das kompakte Pack den erneut gesendeten Kontext um etwa `20%` bis `55%`
- viele reale Läufe lagen ungefähr bei `ein Drittel bis zur Hälfte weniger` wiederholtem Kontext
- wenn ein Ablauf sonst ungefähr `1000` Tokens an früherem Kontext erneut senden müsste, liegt eine vernünftige Erwartung oft eher bei `450` bis `800` Tokens

Beispiele aus lokaler Validierung:

- `401 -> 218` ungefähre Tokens
- `312 -> 144` ungefähre Tokens
- `290 -> 227` ungefähre Tokens
- `337 -> 240` ungefähre Tokens

Wichtig: Das ist keine feste Garantie pro Prompt. Wenn das erzeugte Pack nicht wirklich kleiner als der Quellkontext ist, injiziert `codex-agent-mem` es nicht erneut und behauptet keine Einsparung, die nicht existiert.

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
