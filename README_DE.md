# codex-agent-mem

Weitere Sprachen: [English](./README.md) | [Español](./README_ES.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Portable, auditierbare und local-first Memory-Schicht für Codex und Coding-Agent-Workflows.

codex-agent-mem hält dauerhafte Projektkontinuität außerhalb des Modell-Runtimes, komprimiert sie in kleinere Working Packs und trägt Operational State über Sessions hinweg weiter, damit Codex mit weniger Wiederholung, weniger falschem „fertig“ und mehr Kontrolle über den Kontext weiterarbeiten kann.

Öffentliche Baseline. In kleinen, testbaren Slices gebaut, noch in Weiterentwicklung, aber bereits auf reale Nutzung ausgerichtet.

## Neu in v1.0.0

- Low-Impact-MCP-Profile: `minimal`, `standard` und `full`
- echtes `--read-only`, das mutierende Tools blockiert und Nebenwrites vermeidet
- Lazy SQLite Initialization für ungenutzte MCP-Verbindungen
- kompakte MCP-Antworttexte per Default, vollständiger Payload bleibt in `structuredContent`
- `known_pack_hash` / `not_modified`, damit unveränderte Continuity-Packs nicht erneut gesendet werden
- Runtime-Diagnostik mit Heartbeat, Spawn-Storm-Warnung, optionaler Telemetrie und optionalem Daemon/stdio-Bridge

Sichtbare Releases: [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Verifizierbare Ergebnisse

`codex-agent-mem` enthält eine reproduzierbare Verification-Sandbox und einen öffentlichen Evidence-Export für v1.0.0.

Der aktuelle öffentliche Lauf wurde mit **Codex Desktop, Modell GPT-5.4, Reasoning Effort xhigh** auf synthetischen Fixtures ausgeführt. Er misst Kontextkompression, Wiederverwendungsprüfung mit `known_pack_hash`, Lazy Initialization, minimales Tool-Profil, Read-only-Sicherheit, Response Diet, lokale Telemetrie, Closure Control und ein Beispiel mit Sub-Agents.

Siehe: [Verification Evidence](./docs/verification/) und [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md).

## Was es liefert

### Kontinuität

- **Kompakte Kontinuität statt rohem Replay**: schreibt kleinere `AGENTS.md`-Packs nur dann, wenn Kompression wirklich günstiger ist
- **Persistenter Operational State**: behält Ziel, Constraints, offene Arbeit, Blocker, Definition of Done und Scope-Guardrails
- **Codex-native Integration**: gebaut für `notify`, MCP stdio, optionale `AGENTS.md`-Synchronisierung und defensives Runtime-Cleanup
- **Praktische Token-Ersparnis**: reduziert wiederholten Kontext oft um etwa `20%` bis `55%`, wenn das kompakte Pack gewinnt

### Closure Control

- **Deterministische Closure-Control**: `mem_open_work` und `mem_completion_check` stellen offene Arbeit über alte Abschlussbehauptungen
- **Scope-Erhalt**: trägt Recent Changes, Must-not-drop-Elemente, Blocker und aktive Kontinuität weiter statt nur Entscheidungen

### Governance und Audit

- **Gesteuerte Memory-Auswahl**: wendet Policies, Inheritance und Repairs an, statt alles blind zu mischen
- **Voll lokal und auditierbar**: SQLite + FTS5, Provenance, Health, Snapshots und lokale UI ohne externen Memory-Service

Geeignet für lange Audits, komplexe Projektkontinuität und Sessions, in denen nicht nur Entscheidungen erinnert werden müssen, sondern Scope-Verlust und falsche Abschlüsse verhindert werden sollen.

## Status

`1.0.0` ist die aktuelle Basis-Release.

Was heute funktioniert:

- Codex-`notify`-Ingestion bei `agent-turn-complete`
- lokale SQLite-Persistenz mit FTS5
- heuristische Extraktion von `session_summary`, `decision`, `objective`, `constraint`, `pending_item`, `completed_item`, `blocker` und `completion_claim`
- hierarchische Definition of Done über `project_dod`, `mission_dod` und `session_dod`
- generierte kompakte Continuity-Packs mit ungefährer Token-Schätzung
- Budget-Profile für Packs: `micro`, `normal` und `full`
- optionale `AGENTS.md`-Synchronisierung, wenn das Pack wirklich kleiner als der Quellkontext ist
- Weitergabe von Operational State, damit die nächste Session Ziel, offene Punkte, Blocker und Scope-Guardrails wiederherstellen kann
- deterministische Closure-Control mit `mem_open_work` und `mem_completion_check`
- Delta-Sicht auf neue Änderungen über `mem_recent_changes`
- Scope-Continuity und Must-not-drop-Guardrails über `mem_scope_guard`
- Guardrails gegen falsches „fertig“, wenn noch Pending Items, Blocker oder DoD-Lücken offen sind
- persistierte Closure- und Kompressionsmetriken pro Projekt
- automatische Budgetwahl für Context-Packs bei `budget=auto`
- persistierte Memory-Provenance pro Observation, abrufbar über `mem_provenance`
- Gesundheitsdiagnose pro Projekt über `mem_health`
- Runtime-Diagnose für den MCP-Prozess über `mem_health_runtime`
- versionierte Projektsnapshots über `mem_snapshot_create`, `mem_snapshot_list` und `mem_snapshot_restore`
- gesteuerte Memory-Policies über `mem_policy_validate`, `mem_policy_add`, `mem_policy_list` und `mem_policy_remove`
- selektive Inheritance-Links über `mem_inheritance_add`, `mem_inheritance_list` und `mem_inheritance_remove`
- gesteuerte Repair-Vorschläge und abgeleitete Repair-Events über `mem_repair_propose` und `mem_repair_apply`
- FastAPI-Inspektions-API
- lokale Inspektions-UI unter `/ui`, inklusive Recent Changes, Scope Guard, Provenance, Health, Snapshots und Governance-Status
- lokale Policy-CLI mit `codex-agent-mem-policy`
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
  - `mem_provenance`
  - `mem_health`
  - `mem_health_runtime`
  - `mem_snapshot_list`
  - `mem_snapshot_create`
  - `mem_snapshot_restore`
  - `mem_policy_list`
  - `mem_policy_validate`
  - `mem_policy_add`
  - `mem_policy_remove`
  - `mem_inheritance_list`
  - `mem_inheritance_add`
  - `mem_inheritance_remove`
  - `mem_repair_propose`
  - `mem_repair_apply`
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

Das gibt den `notify`-Block, den Block `[mcp_servers."codex-agent-mem"]`, einen expliziten stdio-Idle-Timeout und die Read-only-Freigaben für die MCP-Tools aus, die du in `~/.codex/config.toml` einfügen kannst.

Wenn du zusätzlich automatische `AGENTS.md`-Reinjektion willst, füge `--sync-project-doc` zum `notify`-Befehl hinzu.

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
