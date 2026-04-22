# codex-agent-mem

Weitere Sprachen: [English](./README.md) | [Español](./README_ES.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Portable, auditierbare und local-first Memory-Schicht für Codex und Coding-Agent-Workflows.

codex-agent-mem hält dauerhafte Projektkontinuität außerhalb des Modell-Runtimes, komprimiert sie in kleinere Working Packs und trägt Operational State über Sessions hinweg weiter, damit Codex mit weniger Wiederholung, weniger falschem „fertig“ und mehr Kontrolle über den Kontext weiterarbeiten kann.

Alles wird lokal durch dieses MCP gespeichert und verarbeitet: SQLite-Datenbank, FTS-Index, Snapshots, Telemetrie-Metadaten und die optionale Inspector-UI. `codex-agent-mem` sendet Memory, Projektdaten, Prompts oder Telemetrie nicht an externe Server.

`codex-agent-mem` entstand für Codex- und GPT-5.x-Workflows, ist aber zu einer portablen MCP-Memory-Schicht für MCP-kompatible Agent-Runtimes gewachsen, darunter Codex CLI, Codex Desktop, Gemini CLI mit Gemini 3.1 Pro, Claude Code mit Opus 4.7 oder Sonnet 4.6 und eigene lokale Agent-Stacks. Es läuft lokal, hält Memory auditierbar und Pull-basiert und sendet gespeicherte Memory nicht an externe Dienste.

Öffentliche Baseline. In kleinen, testbaren Slices gebaut, noch in Weiterentwicklung, aber bereits auf reale Nutzung ausgerichtet.

## Neu in v1.0.0

- Low-Impact-MCP-Profile: `minimal`, `standard` und `full`
- echtes `--read-only`, das mutierende Tools blockiert und Nebenwrites vermeidet
- Lazy SQLite Initialization für ungenutzte MCP-Verbindungen
- kompakte MCP-Antworttexte per Default, vollständiger Payload bleibt in `structuredContent`
- `known_pack_hash` / `not_modified`, damit unveränderte Continuity-Packs nicht erneut gesendet werden
- Runtime-Diagnostik mit Heartbeat, Spawn-Storm-Warnung, optionaler Telemetrie und optionalem Daemon/stdio-Bridge

Sichtbare Releases: [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Snapshot

| Szenario | Quell-Tokens | Pack-Tokens | Ersparnis | `not_modified` | Tools | Lazy init | Read-only |
|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | 1,841 | 216 | 88.27% | true | 4 | false->true | true |
| Medium agent workflow | 4,855 | 233 | 95.20% | true | 4 | false->true | true |
| Large repeated audit | 9,731 | 232 | 97.62% | true | 4 | false->true | true |
| Sub-agent handoff example | 6,523 | 239 | 96.34% | true | 4 | false->true | true |

Über diese reproduzierbaren Fixtures hinweg wurde wiederholter Operational Context von ca. 22.950 Quell-Tokens auf ca. 920 Memory-Pack-Tokens reduziert, also um ungefähr 96,0%. Das ist keine universelle Garantie; es zeigt den Effekt, wenn ein Agent sonst dieselbe Projektkontinuität erneut senden würde.

### Runtime-Validierungs-Snapshot

| Runtime | Setup | Beobachtete Metriken | Ergebnis |
|---|---|---|---|
| Codex Desktop | GPT-5.4, Reasoning Effort xhigh, synthetische v1.0-Fixtures | ca. 22.950 Quell-Tokens -> ca. 920 Pack-Tokens, ca. 96,0% weniger wiederholter Kontext, `not_modified=true` bei wiederholten Packs | Öffentliche reproduzierbare Verifikation |
| Gemini CLI | Gemini 3.1 Pro, `codex-agent-mem` MCP stdio, `standard`, `read-only`, `compact` | stabiler Prozess, Request-Zähler stieg wie erwartet, `mem_search` gab Objektwurzel `{items, count}` mit `count=2` zurück | Live-MCP-Validierung bestanden |
| Claude Code | Claude Opus 4.7, nur `codex-agent-mem` MCP stdio, `standard`, `read-only`, `compact` | Requests `3 -> 8`, Lazy init `false -> true`, `same_db_process_count=2`, `spawn_storm_warning=false`, `mem_search count=2` | Live-MCP-Validierung bestanden |

## Verifizierbare Ergebnisse

`codex-agent-mem` enthält eine reproduzierbare Verification-Sandbox und einen öffentlichen Evidence-Export für v1.0.0.

Der aktuelle öffentliche Lauf wurde mit **Codex Desktop, Modell GPT-5.4, Reasoning Effort xhigh** auf synthetischen Fixtures ausgeführt. Er misst Kontextkompression, Wiederverwendungsprüfung mit `known_pack_hash`, Lazy Initialization, minimales Tool-Profil, Read-only-Sicherheit, Response Diet, lokale Telemetrie, Closure Control und ein Beispiel mit Sub-Agents.

Siehe: [Verification Evidence](./docs/verification/) und [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md).

## Claude Code und claude-mem

`codex-agent-mem` läuft in Claude Code als normaler MCP-stdio-Server. Es installiert keine Session-Start-Hooks, Stop-Hooks oder automatische Post-Turn-Zusammenfassungen. Speicher wird bei Bedarf über MCP-Tools wie `mem_context_pack`, `mem_search`, `mem_open_work` und `mem_completion_check` abgerufen.

Wenn du bereits `claude-mem` nutzt, können beide Tools technisch zusammen laufen. Für Low-Latency-Workflows ist es besser, jeweils nur eine aktive Memory-Schicht zu verwenden. In lokaler Validierung blieb `codex-agent-mem` allein kompakt (`same_db_process_count=2`, `spawn_storm_warning=false`). Zusammen mit `claude-mem` stieg die sichtbare Tool-Oberfläche auf 61 Tools, ein Session-Start-Memory-Block von ca. 6.995 Tokens wurde hinzugefügt, und es traten Post-Turn-Stop-Hook-Verzögerungen auf. Das bricht `codex-agent-mem` nicht, erschwert aber den Vergleich von Ergebnissen und kann die Latenz erhöhen.

Nutze `codex-agent-mem`, wenn du lokale, auditierbare, Pull-basierte Memory mit explizitem Retrieval und deterministischen Closure-Checks bevorzugst. Zusätzliche Memory-Plugins solltest du nur einsetzen, wenn du deren automatisches Hook-basiertes Verhalten bewusst willst.

Für token-sensitive Claude-Code-Workflows ist `codex-agent-mem` bewusst günstig voreingestellt: keine Session-Start-Injektion, keine Stop-Hook-Zusammenfassung, kompakte Antworten, explizite Budgets und `pack_hash` / `not_modified` als Short-Circuit für unveränderte Packs.

## Was es liefert

### Kontinuität

- **Kompakte Kontinuität statt rohem Replay**: schreibt kleinere `AGENTS.md`-Packs nur dann, wenn Kompression wirklich günstiger ist
- **Persistenter Operational State**: behält Ziel, Constraints, offene Arbeit, Blocker, Definition of Done und Scope-Guardrails
- **Codex-native Integration**: gebaut für `notify`, MCP stdio, optionale `AGENTS.md`-Synchronisierung und defensives Runtime-Cleanup
- **Praktische Token-Ersparnis**: reduziert wiederholte Kontinuität, wenn das kompakte Pack gewinnt; die öffentlichen v1.0-Fixtures zeigen 88% bis 97% Reduktion in Repeated-Context-Szenarien

### Closure Control

- **Deterministische Closure-Control**: `mem_open_work` und `mem_completion_check` stellen offene Arbeit über alte Abschlussbehauptungen
- **Scope-Erhalt**: trägt Recent Changes, Must-not-drop-Elemente, Blocker und aktive Kontinuität weiter statt nur Entscheidungen

### Governance und Audit

- **Gesteuerte Memory-Auswahl**: wendet Policies, Inheritance und Repairs an, statt alles blind zu mischen
- **Voll lokal und auditierbar**: SQLite + FTS5, Provenance, Health, Snapshots und lokale UI ohne externen Memory-Service und ohne ausgehende Memory-Synchronisierung

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

## Wie Agenten es verwenden sollten

Nach der Konfiguration sollte der Agent `codex-agent-mem` proaktiv nutzen, wenn Kontinuität relevant ist. Du solltest nicht alle paar Turns erneut "nutze das Memory-MCP" schreiben müssen.

Empfohlenes Muster:

- mit `mem_context_pack` starten, wenn frühere Entscheidungen, offene Arbeit, Blocker, Constraints oder Projektstatus relevant sein können
- bei wiederholten Abfragen `known_pack_hash` übergeben, damit unveränderte Packs `not_modified` zurückgeben statt Kontext erneut zu senden
- `mem_search` nur nutzen, wenn das kompakte Pack nicht ausreicht
- vor einem Abschluss-Claim `mem_open_work` und `mem_completion_check` für Implementierung, Validierung, Veröffentlichung, Migration oder Dokumentation aufrufen

Daraus entsteht die praktische Token-Ersparnis: zuerst kompakte Kontinuität, gezielte Erweiterung nur bei Bedarf, und kein erneutes Senden desselben Packs, wenn sich nichts geändert hat.

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

- die öffentlichen v1.0-Fixtures reduzierten wiederholten Kontext von ca. 22.950 Quell-Tokens auf ca. 920 Pack-Tokens, also ungefähr `96,0%` in diesem kontrollierten Szenario
- einzelne Repeated-Context-Szenarien in der Fixture-Suite lagen zwischen `88%` und `97%` Reduktion
- Live-Checks in Gemini CLI und Claude Code bestätigten kompaktes MCP-Retrieval, stabilen Prozess-Lifecycle, Read-only-Modus und Objektwurzel-Antworten für `mem_search`

Beispiele aus der öffentlichen v1.0-Verification-Sandbox:

- `1,841 -> 216` ungefähre Tokens
- `4,855 -> 233` ungefähre Tokens
- `9,731 -> 232` ungefähre Tokens
- `6,523 -> 239` ungefähre Tokens

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
