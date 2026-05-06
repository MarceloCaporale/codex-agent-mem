# codex-agent-mem

Weitere Sprachen: [English](./README.md) | [Español](./README_ES.md) | [Português do Brasil](./README_PT_BR.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

**Portable, auditierbare und local-first MCP-Memory fuer MCP-kompatible AI-Agents und Coding-Workflows.**

codex-agent-mem hält dauerhafte Projektkontinuität außerhalb des Modell-Runtimes, komprimiert sie in kleinere Working Packs und trägt Operational State über Sessions hinweg weiter, damit MCP-kompatible AI-Agents mit weniger Wiederholung, weniger falschem „fertig“ und mehr Kontrolle über den Kontext weiterarbeiten können.

Alles wird lokal durch dieses MCP gespeichert und verarbeitet: SQLite-Datenbank, FTS-Index, Snapshots, Telemetrie-Metadaten und die optionale Inspector-UI. `codex-agent-mem` sendet Memory, Projektdaten, Prompts oder Telemetrie nicht an externe Server. MCP-Clients koennen Tool-Ergebnisse trotzdem an das konfigurierte Modell oder den konfigurierten Dienst weitergeben; behandle abgerufene Memory daher als lokale Tool-Ausgabe, die an diesen Client uebergeben wird.

Ursprünglich für Codex- und GPT-Workflows gebaut, ist `codex-agent-mem` zu einer portablen MCP-Memory-Schicht für MCP-kompatible Runtimes gewachsen, darunter Codex CLI/Desktop, Claude Code, Google Gemini CLI, Qwen-Code-Workflows mit Ollama-Modellen und andere lokale oder Drittanbieter-CLI-Agent-Stacks. Die Validierung wird pro Client/Runtime und Evidenzstufe nachverfolgt. Modellspezifische Details stehen in den Validierungsdokumenten, damit dieses README die öffentliche Oberfläche beschreibt, ohne einen einzelnen Runtime zu überzeichnen.

`codex-agent-mem` läuft lokal, hält Memory auditierbar und Pull-basiert und sendet gespeicherte Memory nicht an externe Dienste.

Öffentliche Baseline. In kleinen, testbaren Slices gebaut, noch in Weiterentwicklung, aber bereits auf reale Nutzung ausgerichtet.

## Neu in v1.0.x

- v1.0.1 behebt einen lokalen Daemon/stdio-Bridge-Idle-Timeout-Pfad, der bei Nutzung von `--daemon-url` als falscher `Transport closed`-Vorfall erscheinen konnte.
- v1.0.1 serialisiert die gemeinsame Request-Verarbeitung im optionalen threaded lokalen Daemon, damit eine einzelne SQLite-gestuetzte Serverinstanz nicht parallel angesteuert wird.
- v1.0.1 haertet die oeffentliche local-first Daemon-Oberflaeche: nur Loopback-Bind, optionales Bearer-Token fuer `/mcp`, bereinigtes `/health` und Token-Weitergabe aus der stdio-Bridge.
- v1.0.1 ergaenzt eine Guardrail zur Instruktionshierarchie im generierten Kontext: abgerufene Memory ist beratender Projektkontext, keine Instruktion hoeherer Prioritaet; das ist eine Basis-Guardrail, kein vollstaendiger Prompt-Injection-Schutz.
- v1.0.1 dokumentiert, dass lokale SQLite-Memory in der oeffentlichen 1.0.x-Linie standardmaessig Klartext ist und nicht als Secrets-Vault behandelt werden darf.
- v1.0.1 normalisiert MCP-Payloads von Tools, die Listen zurueckgeben, sodass `structuredContent` Objektwurzeln wie `{items, count}` statt Root-Arrays nutzt; das verbessert Kompatibilitaet mit strengeren Clients wie Claude Code.
- v1.0.1 ergaenzt session-aware Retrieval fuer persistierte Memory: `mem_session_list` listet aktuelle Sessions, `mem_scope_resolve` priorisiert persistierte Lanes aus expliziten Hints, `mem_bootstrap_context` vermeidet Project-wide Startup-Packs bei mehrdeutigen Containern, und optionales `session_id` filtert Retrieval-Tools, damit breite Project Scopes keine Chats oder Agents mischen. Project-wide Packs, die mehrere Sessions oder inferierte Sub-Scopes umfassen, senden eine sichtbare Scope-Warnung und empfehlen Narrowing, bevor der Pack als aktiver Kontext behandelt wird. Das ist keine Live-Awareness des aktuellen Turns.
- v1.0.1 haelt normale Continuity-Installationen writable; `--read-only` ist ein expliziter Audit-/Debug-/Retrieval-only-Modus, nicht der operative Default.

- Low-Impact-MCP-Profile: `minimal`, `standard` und `full`
- expliziter `--read-only` Audit-/Debug-Modus, der mutierende Tools blockiert und Nebenwrites vermeidet
- Lazy SQLite Initialization für ungenutzte MCP-Verbindungen
- kompakte MCP-Antworttexte per Default, vollständiger Payload bleibt in `structuredContent`
- `known_pack_hash` / `not_modified`, damit unveränderte Continuity-Packs nicht erneut gesendet werden
- Runtime-Diagnostik mit Heartbeat, Spawn-Storm-Warnung, optionaler Telemetrie und optionalem Daemon/stdio-Bridge

Sichtbare Releases: [v1.0.1 Transport + Local Security Hotfix](./CHANGELOG.md#101---prepared-2026-05-06) | [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Snapshot (synthetische v1.0-Fixtures)

| Szenario | Profil | Quell-Tokens | Pack-Tokens | Ersparnis | `not_modified` | Tools | Lazy init | Read-only |
|---|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | `minimal` | 1,841 | 253 | 86.26% | true | 4 | false->true | true |
| Medium agent workflow | `minimal` | 4,855 | 270 | 94.44% | true | 4 | false->true | true |
| Large repeated audit | `minimal` | 9,731 | 269 | 97.24% | true | 4 | false->true | true |
| Sub-agent handoff example | `minimal` | 6,523 | 276 | 95.77% | true | 4 | false->true | true |

Über diese reproduzierbaren Fixtures hinweg wurde wiederholter Operational Context von ca. 22.950 Quell-Tokens auf ca. 1.068 Memory-Pack-Tokens reduziert, also um ungefähr 95,35%. Das ist keine universelle Garantie; es zeigt den Effekt, wenn ein Agent sonst dieselbe Projektkontinuität erneut senden würde.

`Tools=4` bezieht sich auf das in diesen Fixtures verwendete pre-session-aware Profil `minimal`. In v1.0.1 enthält `minimal` zusätzlich `mem_session_list`, `mem_scope_resolve` und `mem_bootstrap_context`, und das Profil `standard` stellt 20 Tools für breitere Retrieval-, Governance- und Audit-Workflows bereit.

### Runtime-Validierungs-Snapshot

| Runtime | Setup | Beobachtete Metriken | Ergebnis |
|---|---|---|---|
| Writable MCP Default | Lokale Codex/Gemini/Claude-Bridges, `read_only=false`; `full`, wenn writable Tools erforderlich sind | `mem_note_create` schrieb indexierte manuelle Notizen und `mem_search` / `mem_context_pack` fanden sie wieder; `mem_snapshot_create(project_key, label, session_id)` schrieb High-Confidence-Provenance | Writable Manual-Note- und Snapshot-Provenance-Smokes bestanden |
| Codex Desktop | Codex Desktop, MCP stdio, explizite retrieval-only v1.0-Fixture mit `minimal`, `read-only`, `compact` | ca. 22.950 Quell-Tokens -> ca. 1.068 Pack-Tokens, ca. 95,35% weniger wiederholter Kontext, `not_modified=true` bei wiederholten Packs | Retrieval-only MCP-Validierung plus öffentliche reproduzierbare Verifikation; writable Continuity ist in der vorherigen Zeile abgedeckt |
| Codex CLI / `codex exec` | Codex-CLI-MCP-stdio-Pfad, kurzlebige / ephemere Ausführung | derselbe lokale MCP-Server und derselbe Konfigurationsstil wie Desktop; der kurzlebige CLI-Lifecycle wurde getrennt vom Long-lived-Desktop-Host-Verhalten validiert | Validierter Codex-CLI-Pfad |
| Google Gemini CLI | `codex-agent-mem` MCP stdio, explizite retrieval-only Validierung mit `standard`, `read-only`; `compact`, wenn strukturierte Payloads sichtbar sind, sonst `verbose` | stabiler Prozess, Request-Zähler stieg wie erwartet, Objektwurzel-Payloads wurden dort geprüft, wo sie sichtbar waren | Retrieval-only MCP-Validierung mit Client-Exposure-Caveat |
| Claude Code | Claude Opus 4.7, nur `codex-agent-mem` MCP stdio, explizite retrieval-only Validierung mit `standard`, `read-only`, `compact` | Requests `3 -> 8`, Lazy init `false -> true`, `same_db_process_count=2` mit einem aktiven Claude-Code-Host, `spawn_storm_warning=false`, `mem_search count=2` | Retrieval-only MCP-Validierung bestanden |
| Qwen Code | Qwen Code 0.15.0, lokales Ollama, `qwen3.6:latest`, explizite retrieval-only Validierung mit `standard`, `read-only`, `compact` | echte MCP-Aufrufe an `mem_context_pack`, `mem_search`, `mem_open_work`, `mem_completion_check`, `mem_health_runtime`; Requests `8`, Lazy init `true`, `spawn_storm_warning=false`, `not_modified=true` | Lokale retrieval-only MCP-Validierung bestanden |
| Lokale Qwen-Modell-Smokes | Qwen Code 0.15.0 mit Ollama-Modellen `qwen3.6:35b-a3b-q8_0` und `qwen3.5:9b` | beide Modelle bestanden CLI-Smokes und riefen `mem_health_runtime` über MCP stdio auf; retrieval-only `read_only=true`, saubere `stdin_eof`-Exits | Lokale retrieval-only Smokes bestanden |
| DeepSeek-V3.2 | Qwen Code 0.15.0, `deepseek-v3.2:cloud` über Ollama Cloud, explizite retrieval-only Validierung mit `standard`, `read-only`, `compact` | echte MCP-Aufrufe an `mem_context_pack`, `mem_search`, `mem_health_runtime`; Requests `6`, `spawn_storm_warning=false`, `not_modified=true` | Retrieval-only MCP-Validierung mit Cloud-Backend bestanden |
| Minimax M2.5 | Qwen Code 0.15.0, `minimax-m2.5:cloud` über Ollama Cloud, explizite retrieval-only Validierung mit `standard`, `read-only`, `compact` | echte MCP-Aufrufe an `mem_context_pack`, `mem_search`, `mem_health_runtime`; Requests `6`, `not_modified=true` | Retrieval-only MCP-Validierung mit Cloud-Backend bestanden |
| Kimi Code CLI | Kimi Code CLI 1.38.0, `codex-agent-mem` MCP stdio, explizite retrieval-only Validierung mit `standard`, `read-only`, `compact` | `kimi mcp test codex-agent-mem` verband sich erfolgreich und listete die erwarteten Standard-Profil-Tools; die vollständige Tool-Call-Validierung mit Kimi K2.5 / Kimi K2.6 bleibt in kontinuierlicher Evaluierung | Retrieval-only MCP-Verbindung validiert; Modelllauf nicht behauptet |
| Grok / xAI | Hinweis zur Protokollkompatibilität | MCP-stdio- / JSON-RPC-Protokollverhalten geprüft | Protokollhinweis |

Grok / xAI ist als Hinweis zur Protokollkompatibilität aufgeführt, nicht als Live-Validierung von Modell-Tool-Calls. Die live validierten Zeilen sind die direkt gemessenen MCP-Client-/Modell-Paare: Codex Desktop/CLI, Google Gemini CLI, Claude Code, Qwen Code, lokale Qwen-Modell-Smokes, DeepSeek-V3.2 über Ollama Cloud, Minimax M2.5 über Ollama Cloud und die Kimi-Code-CLI-Verbindungsvalidierung. Allgemein ist `codex-agent-mem` auf der MCP-Schicht modellagnostisch; neue Paare werden ergänzt, sobald ihre Live-Messungen vorliegen.

## Verifizierbare Ergebnisse

`codex-agent-mem` enthält eine reproduzierbare Verification-Sandbox und einen öffentlichen Evidence-Export für v1.0.0. Der Fixture-Ansatz ist absichtlich gewählt: Das MCP optimiert wiederholbare Operational-Context-Verarbeitung, deshalb hält die öffentliche Evidenz den wiederholten Kontext kontrolliert, statt jeden Lauf zu einer anderen Unterhaltung zu machen.

Die öffentliche v1.0.x-Evidenz kombiniert reproduzierbare Verifikations-Fixtures mit Live-MCP-Runtime-Validierung über die oben gelisteten Runtimes. Sie misst Kontextkompression, Wiederverwendungsprüfung mit `known_pack_hash`, Lazy Initialization, minimales Tool-Profil, Sicherheit des expliziten Read-only-Modus, Response Diet, lokale Telemetrie, Closure Control und ein Beispiel mit Sub-Agents.

Siehe: [Verification Evidence](./docs/verification/) und [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md).

## Claude Code und claude-mem

`codex-agent-mem` läuft in Claude Code als normaler MCP-stdio-Server. Es installiert keine Session-Start-Hooks, Stop-Hooks oder automatische Post-Turn-Zusammenfassungen. Speicher wird bei Bedarf über MCP-Tools wie `mem_context_pack`, `mem_search`, `mem_open_work` und `mem_completion_check` abgerufen.

Wenn du bereits `claude-mem` nutzt, können beide Tools technisch zusammen laufen. Für Workflows mit weniger Overhead und geringerer Latenz ist es besser, jeweils nur eine aktive Memory-Schicht zu verwenden. In lokaler Validierung mit einem aktiven Claude-Code-Host blieb `codex-agent-mem` allein kompakt (`same_db_process_count=2`, `spawn_storm_warning=false`). Zusammen mit `claude-mem` stieg die sichtbare Tool-Oberfläche auf 61 Tools, ein Session-Start-Memory-Block von ca. 6.995 Tokens wurde hinzugefügt, und es traten Post-Turn-Stop-Hook-Verzögerungen auf. Das bricht `codex-agent-mem` nicht, erschwert aber den Vergleich von Ergebnissen und kann Overhead und Latenz erhöhen.

Nutze `codex-agent-mem`, wenn du lokale, auditierbare, Pull-basierte Memory mit explizitem Retrieval und deterministischen Closure-Checks bevorzugst. Zusätzliche Memory-Plugins solltest du nur einsetzen, wenn du deren automatisches Hook-basiertes Verhalten bewusst willst.

Für token-sensitive Claude-Code-Workflows ist `codex-agent-mem` auf niedrigen Overhead voreingestellt: keine Session-Start-Injektion, keine Stop-Hook-Zusammenfassung, kompakte Antworten, explizite Budgets und `pack_hash` / `not_modified` als Short-Circuit für unveränderte Packs.

## Optionaler Begleiter: clean-process-ended

`codex-agent-mem` v1.0.1 und `clean-process-ended` ([GitHub](https://github.com/MarceloCaporale/clean-process-ended)) v0.7.2 funktionieren unabhängig voneinander, lösen aber benachbarte Probleme in lokalen Agent-Workflows.

- `codex-agent-mem` bewahrt Kontinuität: Projekt-Memory, scoped Context Packs, manuelle Notizen, Snapshots, offene Arbeit, Blocker und deterministische Closure-Checks.
- `clean-process-ended` behandelt lokale Prozesshygiene: Ownership-first-Diagnostik, Dry-run-Close-Checks und kompakte Janitor-Receipts.

Zusammen verbessern sie End-of-Task-Workflows: Kontext wiederherstellen, Arbeit abschliessen, lokalen Prozessstatus prüfen und kompakte Close-Evidence speichern, ohne eines der beiden MCPs zur harten Abhängigkeit des anderen zu machen.

## Was es liefert

### Kontinuität

- **Kompakte Kontinuität statt rohem Replay**: schreibt kleinere `AGENTS.md`-Packs nur dann, wenn Kompression wirklich günstiger ist
- **Persistenter Operational State über Sessions und Agents hinweg**: behält Ziel, Constraints, offene Arbeit, Blocker, Definition of Done und Scope-Guardrails, damit Kontext nicht an ein einzelnes Modell, eine einzelne Session oder eine Provider-UI gebunden bleibt
- **MCP-native Integration**: läuft als lokaler MCP-stdio-Server für Codex, Claude Code, Google Gemini CLI, Qwen Code und andere MCP-kompatible Clients; Codex-`notify` und optionale `AGENTS.md`-Synchronisierung bleiben verfügbar, wenn sie nützlich sind
- **Token-Effizienz für Agent-Workflows**: verbessert die Token-Ökonomie wiederholter Agent-Arbeit, indem Kontinuitäts-Replay reduziert wird, wenn das kompakte Pack gewinnt; die öffentlichen v1.0-Fixtures zeigen 86% bis 97% Reduktion in Repeated-Context-Szenarien

### Closure Control

- **Deterministische Closure-Control**: `mem_open_work` und `mem_completion_check` stellen offene Arbeit über alte Abschlussbehauptungen
- **Scope-Erhalt**: trägt Recent Changes, Must-not-drop-Elemente, Blocker und aktive Kontinuität weiter statt nur Entscheidungen

### Governance und Audit

- **Gesteuerte Memory-Auswahl**: wendet Policies, Inheritance und Repairs an, statt alles blind zu mischen
- **Inspizierbare MCP-Memory**: die lokale `/ui` erlaubt Navigation durch Recent Changes, Scope Guard, Provenance, Health, Snapshots, Governance-Status und gespeicherte Memory, ohne die SQLite-Datenbank manuell zu öffnen
- **Voll lokal und auditierbar**: SQLite + FTS5, Provenance, Health, Snapshots und lokale UI ohne externen Memory-Service und ohne ausgehende Memory-Synchronisierung
- **Klare lokale Sicherheitsgrenze**: v1.0.1 härtet Loopback-Daemon-Zugriff, optionale Bearer-Token-Auth, bereinigtes `/health` und die Instruktionshierarchie des generierten Kontexts; das ist kein vollständiger Prompt-Injection-Schutz, und die öffentliche 1.0.x-SQLite-Datenbank bleibt standardmäßig Klartext und sollte nicht als Secrets-Vault genutzt werden

Wichtige Dokumente: [AGENTS.md](./AGENTS.md) | [Quickstart](./docs/quickstart.md) | [Codex-Integration](./docs/codex-integration.md) | [Codex-Desktop-Notiz](./docs/codex-desktop-lifecycle-note.md) | [Support Matrix](./docs/support-matrix.md) | [Design Decisions](./docs/design-decisions.md)

Geeignet für lange Audits, komplexe Projektkontinuität und Sessions, in denen nicht nur Entscheidungen erinnert werden müssen, sondern Scope-Verlust und falsche Abschlüsse verhindert werden sollen.

## Status

`1.0.1` ist die aktuelle 1.0.x-Wartungsrelease. `1.0.0` bleibt die oeffentliche Verifikationsbasis fuer die reproduzierbaren Metriken unten.

Was heute funktioniert:

- Codex-`notify`-Ingestion bei `agent-turn-complete`
- lokale SQLite-Persistenz mit FTS5
- heuristische Extraktion von `session_summary`, `decision`, `objective`, `constraint`, `pending_item`, `completed_item`, `blocker` und `completion_claim`
- hierarchische Definition of Done über `project_dod`, `mission_dod` und `session_dod`
- generierte kompakte Continuity-Packs mit ungefährer Token-Schätzung
- Budget-Profile für Packs: `micro`, `normal` und `full`
- optionale `AGENTS.md`-Synchronisierung über `--sync-project-doc`, wenn das Pack wirklich kleiner als der Quellkontext ist
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
- manuelle operative Notizen über `mem_note_create`, indexiert für `mem_search` und geeignet für `mem_context_pack`
- versionierte Projektsnapshots über `mem_snapshot_create`, `mem_snapshot_list` und `mem_snapshot_restore`
- gesteuerte Memory-Policies über `mem_policy_validate`, `mem_policy_add`, `mem_policy_list` und `mem_policy_remove`
- selektive Inheritance-Links über `mem_inheritance_add`, `mem_inheritance_list` und `mem_inheritance_remove`
- gesteuerte Repair-Vorschläge und abgeleitete Repair-Events über `mem_repair_propose` und `mem_repair_apply`
- Low-Impact-MCP-Profile über `--profile minimal|standard|full`
- expliziter Read-only-Audit-/Debug-Modus über `--read-only`
- kompakter MCP-Antworttext mit vollständigem `structuredContent`
- Continuity-Pack-Reuse über `known_pack_hash` / `not_modified`
- kurzer In-Process-Cache für teure Read-Tools
- Lazy SQLite Initialization für günstige ungenutzte MCP-Verbindungen
- angereicherte Runtime Health mit Profil, Mutability, Cache, Lazy Init, Heartbeat und Spawn-Storm-Diagnose
- optionale lokale Runtime-Telemetrie über `--telemetry-mode off|summary|debug`
- optionaler lokaler Daemon über `codex-agent-mem-daemon` und stdio-Bridge-Modus mit `--daemon-url`
- FastAPI-Inspektions-API
- lokale Inspektions-UI unter `/ui`, inklusive Recent Changes, Scope Guard, Provenance, Health, Snapshots und Governance-Status
- lokale Policy-CLI mit `codex-agent-mem-policy`
- MCP-stdio-Server mit:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_session_list`
  - `mem_scope_resolve`
  - `mem_bootstrap_context`
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
  - `mem_note_create`
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

## Warum dieses Repository existiert

- Agent-Workflows brauchen oft dauerhaften Kontext außerhalb eines einzelnen Runtime-Prozesses.
- Retrieval allein löst den größeren Fehler nicht: Scope geht verloren und Nutzer müssen früheren Kontext wiederholen.
- Ein kompakter Continuity-Block oder MCP Context Pack kann reduzieren, wie viel alter Kontext manuell wiederholt werden muss.
- Nur Entscheidungen mitzunehmen reicht nicht; der Runtime braucht auch aktives Ziel, offene Arbeit, Blocker und eine Regel gegen falschen Abschluss.
- SQLite hält die Implementierung local-first, auditierbar und leicht inspizierbar.
- Die aktuelle Release fokussiert bewusst einen schmalen, testbaren Slice statt einer breiten unfertigen Plattform.
- Langlebige und kurzlebige MCP-Hosts können sich unter Last unterschiedlich verhalten; die Validierungsdokumente definieren die genaue Runtime-Grenze.

## Installationsmodell

`codex-agent-mem` wird als lokales Python-Paket installiert und MCP-kompatiblen Clients über stdio-Kommandos bereitgestellt.

Das stabile Muster ist:

1. Paket installieren
2. den MCP-Client auf das installierte Kommando zeigen lassen
3. die Memory-Datenbank lokal und auditierbar halten

Codex-spezifische Snippets für `notify` und `mcp_servers` erzeugt `codex-agent-mem-bootstrap-codex`; andere MCP-Clients verwenden ihre eigenen Konfigurationsdateien.

## Quickstart

Wenn du den kürzesten Weg vom Clone zu einem funktionierenden lokalen Setup willst:

### PowerShell / Windows

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### bash / macOS / Linux

```bash
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

Für Codex fügst du das erzeugte Snippet in `~/.codex/config.toml` ein. Für andere MCP-Clients nutze den gemeinsamen stdio-Befehl in [MCP-Clients konfigurieren](#mcp-clients-konfigurieren).

## Installation

### Option A: `pipx` von GitHub

Direkt von der Repository-URL installieren:

```bash
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

### Option B: lokale Entwicklungsinstallation

```bash
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

## MCP-Clients konfigurieren

Der Einstiegspunkt des MCP-Servers ist für jeden kompatiblen Client derselbe:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Zeige deinen MCP-fähigen Client auf dieses installierte stdio-Kommando. Die öffentlich validierten v1.0.x-Pfade umfassen Codex CLI/Desktop, Claude Code, Google Gemini CLI, Qwen Code mit lokalen Qwen-Modellen über Ollama, DeepSeek-V3.2 und Minimax M2.5 über Ollama Cloud sowie Kimi Code CLI Verbindungsvalidierung.

### Codex-Helfer

Ein sofort einsetzbares Snippet erzeugen:

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Für Codex gibt das den `notify`-Block, den Block `[mcp_servers."codex-agent-mem"]`, einen expliziten stdio-Idle-Timeout und die Freigaben für die MCP-Tools aus, die du in `~/.codex/config.toml` einfügen kannst.

Für langlebige Codex-Desktop-Sessions ist ein längeres MCP-Idle-Timeout sinnvoll, zum Beispiel `--idle-timeout-seconds 1800`, damit der Desktop-Thread seltener einen geschlossenen stdio-Transport hält. Für kurze CLI- oder `codex exec`-Läufe reichen `300` Sekunden meist aus und räumen schneller auf.

Wenn du zusätzlich automatische `AGENTS.md`-Reinjektion willst, füge `--sync-project-doc` zum `notify`-Befehl hinzu.

## Wie Agenten es verwenden sollten

Nach der Konfiguration sollte der Agent `codex-agent-mem` proaktiv nutzen, wenn Kontinuität relevant ist. Du solltest nicht alle paar Turns erneut "nutze das Memory-MCP" schreiben müssen.

Empfohlenes Muster:

- mit `mem_bootstrap_context` starten, wenn frühere Entscheidungen, offene Arbeit, Blocker, Constraints oder Projektstatus relevant sein können; Chat-Titel, Thread, cwd oder Repo-Hints uebergeben, wenn der Host sie bereitstellt
- `mem_context_pack` direkt nur aufrufen, wenn der Scope bereits explizit ist, in breiten Workspaces idealerweise mit `session_id`
- bei wiederholten Abfragen `known_pack_hash` übergeben, damit unveränderte Packs `not_modified` zurückgeben statt Kontext erneut zu senden
- `mem_search` nur nutzen, wenn das kompakte Pack nicht ausreicht
- vor einem Abschluss-Claim `mem_open_work` und `mem_completion_check` für Implementierung, Validierung, Veröffentlichung, Migration oder Dokumentation aufrufen

Daraus entsteht die praktische Token-Ökonomie: zuerst kompakte Kontinuität, gezielte Erweiterung nur bei Bedarf, und kein erneutes Senden desselben Packs, wenn sich nichts geändert hat.

Beispieldateien liegen unter [examples/codex](./examples/codex/), Hinweise zu Ollama-gestützten Workflows unter [examples/ollama](./examples/ollama/).

## Lokal ausführen

Die Inspektions-API starten:

```bash
codex-agent-mem-api --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Danach im Browser öffnen:

```text
http://127.0.0.1:37770/ui
```

Den MCP-Server starten:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Der aktuelle MCP-Transport ist stdio. Ein Prozess pro Host-Verbindung ist normal; es ist kein Singleton-Daemon. Das defensive Idle-Timeout lässt ungenutzte oder verwaiste Instanzen sauber beenden.

Empfohlene Defaults: ein längeres Timeout für Codex-Desktop-Sessions, zum Beispiel `1800` Sekunden, und ein kürzeres Timeout für CLI-/ephemere Läufe, zum Beispiel `300` Sekunden.

Den generierten Continuity-Block für ein Verzeichnis manuell neu bauen:

```bash
codex-agent-mem-refresh-context --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db" --project-key YOUR_PROJECT --cwd /path/to/project
```

```powershell
codex-agent-mem-refresh-context --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --project-key YOUR_PROJECT --cwd C:\Path\To\Project
```

## Schnelle Verifikation

Den Smoke-Test ausführen:

```bash
codex-agent-mem-smoke --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Dadurch wird ein Beispiel-Turn eingefügt, Beobachtungen werden extrahiert und die letzte Retrieval-Sicht sowie die `project_brief`-Erzeugung verifiziert.

## Token-Effizienz: was heute Tokens spart

- Das Paket baut aus aktuellen Turns, dauerhaften Entscheidungen und abgeleitetem operativem Zustand ein kleineres Working-Memory-Pack.
- Wenn `--sync-project-doc` aktiv ist und dieses Pack wirklich kleiner als der Quellkontext ist, wird es für das Arbeitsverzeichnis in `AGENTS.md` synchronisiert.
- MCP-Retrieval und optionale `AGENTS.md`-Synchronisierung lassen neue Sessions mit komprimierter Kontinuität starten, statt alten Scope erneut zu erklären.
- `mem_context_pack` stellt dasselbe kompakte Pack über MCP für On-Demand-Retrieval bereit.
- Das Pack trägt offene Arbeit und Blocker weiter, sodass ein späterer Lauf "was bleibt" und nicht nur "was entschieden wurde" rekonstruieren kann.

Das ist Token-Effizienz für Agent-Workflows, keine magische Kompression. `codex-agent-mem` verbessert die Kontext-Ökonomie, indem es wiederholten Projektkontext reduziert, unveränderte Packs mit `known_pack_hash` wiederverwendet und Agents nur die Memory erweitern lässt, die sie wirklich brauchen.

## Ungefähre Token-Einsparung

Einfach gesagt: Das Ziel ist, die Menge des wiederholten Kontexts zu verringern, die man dem Agenten erneut geben muss. Es beseitigt diese Wiederholung nicht vollständig, kann sie aber spürbar verkleinern.

Was wir aus lokaler Validierung ehrlich sagen können:

- die öffentlichen v1.0-Fixtures reduzierten wiederholten Kontext von ca. 22.950 Quell-Tokens auf ca. 1.068 Pack-Tokens, also ungefähr `95,35%` in diesem kontrollierten Szenario
- einzelne Repeated-Context-Szenarien in der Fixture-Suite lagen zwischen `86%` und `97%` Reduktion
- Live-Checks bestätigten kompaktes MCP-Retrieval, stabilen Prozess-Lifecycle, Objektwurzel-/No-Reinjection-Verhalten soweit sichtbar und writable Snapshot-Provenance in den lokalen Codex/Gemini/Claude-Bridges

Beispiele aus der öffentlichen v1.0-Verification-Sandbox:

- `1,841 -> 253` ungefähre Tokens
- `4,855 -> 270` ungefähre Tokens
- `9,731 -> 269` ungefähre Tokens
- `6,523 -> 276` ungefähre Tokens

Wichtig: Das ist keine feste Garantie pro Prompt. Wenn das erzeugte Pack nicht wirklich kleiner als der Quellkontext ist, injiziert `codex-agent-mem` es nicht erneut und behauptet keine Einsparung, die nicht existiert.

## Was es heute erkennen hilft

- das ursprüngliche Ziel nach einigen Läufen zu verlieren
- Scope stillschweigend zu verengen, obwohl der Nutzer mehr verlangt hat
- Abschluss zu melden, obwohl noch Arbeit offen ist
- Blocker zu vergessen und den nächsten Lauf so zu beginnen, als wäre die Aufgabe erledigt

## Repository-Struktur

- [src/codex_agent_mem](./src/codex_agent_mem/) - Paketcode
- [tests](./tests/) - ausführbare Tests
- [examples/codex](./examples/codex/) - Codex-Integrationsbeispiele
- [examples/ollama](./examples/ollama/) - Hinweise zu Ollama-gestützten Workflows
- [scripts](./scripts/) - lokale Bootstrap-Helfer
- [docs](./docs/) - Architektur und Release-Hinweise

## Dokumentationskarte

- [AGENTS.md](./AGENTS.md) - Repo-Karte und operative Anleitung für MCP-kompatible AI-Agents
- [docs/quickstart.md](./docs/quickstart.md) - kürzester Installations- und First-Run-Pfad
- [docs/codex-integration.md](./docs/codex-integration.md) - wie notify und MCP in Codex zusammenpassen
- [docs/verification](./docs/verification/) - reproduzierbare öffentliche Metriken und v1.0.0-Evidenz
- [docs/support-matrix.md](./docs/support-matrix.md) - aktueller Support und bekannte Lücken
- [docs/codex-desktop-lifecycle-note.md](./docs/codex-desktop-lifecycle-note.md) - beobachtetes Codex-Desktop-Lifecycle-Verhalten und praktische Mitigations
- [docs/design-decisions.md](./docs/design-decisions.md) - explizite Produkt- und Architekturentscheidungen
- [docs/architecture.md](./docs/architecture.md) - portable technische Architektur der aktuellen Release
- [docs/validation](./docs/validation/) - Validierungsstufen, Runtime-Support, Client-Verhalten und öffentliche Evidenznotizen
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contribution-Workflow und Qualitätsstandard
- [SECURITY.md](./SECURITY.md) - Support-Scope und Security-Reporting
- [docs/discoverability.md](./docs/discoverability.md) - empfohlene GitHub-Beschreibung, Topics und Release-Framing

## Release-Oberfläche

Dieses Repository enthält:

- sauberes Root-Layout
- installierbares `pyproject.toml`
- Kommando-Entry-Points
- Tests
- CI-Workflow
- Lizenz
- Changelog

## Autor

Erstellt und gepflegt von Marcelo Caporale.

- X: [@MarceloCaporale](https://x.com/MarceloCaporale)
- Studio: [Visual AI Media](https://visualaimedia.com)
- Lab: [Visual Systems Lab](https://visualsystemslab.com)
