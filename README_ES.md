# codex-agent-mem

<p align="center">
  <img src="docs/assets/codex-agent-mem-social-preview.png" alt="codex-agent-mem: persistent local memory for MCP clients" width="100%">
</p>

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/MarceloCaporale/codex-agent-mem)

Otros idiomas: [English](./README.md) | [Deutsch](./README_DE.md) | [Português do Brasil](./README_PT_BR.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

**Memoria MCP portable, auditable y local-first para agentes de IA y flujos de coding compatibles con MCP.**

codex-agent-mem conserva memoria duradera fuera del runtime del modelo, comprime continuidad en packs mas chicos, y arrastra estado operativo para que agentes de IA compatibles con MCP retomen con menos repeticion, menos cierres falsos y mas control sobre lo que entra en contexto.

Todo se guarda y procesa localmente en este MCP: base SQLite, indice FTS, snapshots, metadata de telemetria y UI opcional de inspeccion. `codex-agent-mem` no envia tu memoria, datos del proyecto, prompts ni telemetria a ningun servidor externo. Los clientes MCP pueden exponer resultados de herramientas al modelo o servicio que configures, asi que trata la memoria recuperada como salida local de herramienta entregada a ese cliente.

Nacido para Codex y flujos GPT, `codex-agent-mem` crecio hasta convertirse en una capa portable de memoria MCP para runtimes compatibles con MCP, incluidos Codex CLI/Desktop, Claude Code, Google Gemini CLI, flujos Qwen Code usando modelos Ollama y otros stacks locales o de terceros para agentes CLI. La validacion se registra por cliente/runtime y nivel de evidencia. Los detalles especificos por modelo quedan en los docs de validacion para que este README describa la superficie publica sin sobredimensionar ningun runtime.

`codex-agent-mem` vive en local, mantiene la memoria auditable y bajo demanda, y no envia tu memoria almacenada a ningun servicio externo.

Baseline publica. Construida en slices chicos y verificables, todavia en evolucion, pero ya pensada para uso real.

## Novedades v1.0.x

- v1.0.2 corrige un caso borde de identidad de proyecto en el que el contexto generado por `codex-agent-mem` dentro de `AGENTS.md` podia confundirse con el scope activo del proyecto en hosts MCP o clientes de agentes. Tambien permite que las notas manuales inicialicen un registro local de proyecto faltante y conserva la metadata `root_path` existente ante actualizaciones conflictivas.
- v1.0.1 corrige un camino de `idle-timeout` entre el daemon local y el bridge stdio que podia aparecer como falso incidente `Transport closed` cuando se usa `--daemon-url`.
- v1.0.1 serializa el manejo compartido de requests dentro del daemon local threaded opcional para que una unica instancia SQLite no sea usada de forma concurrente.
- v1.0.1 endurece la superficie publica local-first del daemon: bind solo a loopback, bearer token opcional para `/mcp`, `/health` sanitizado y reenvio de token desde el bridge stdio.
- v1.0.1 agrega una guardrail de jerarquia de instrucciones en el contexto generado: la memoria recuperada es contexto auxiliar de proyecto, no una instruccion de mayor prioridad; es una guardrail basica, no una proteccion completa contra prompt injection.
- v1.0.1 documenta que la memoria SQLite local es texto plano por defecto en la linea publica 1.0.x y no debe tratarse como vault de secretos.
- v1.0.1 normaliza los payloads MCP de tools que devuelven listas para que `structuredContent` use raices objeto como `{items, count}` en vez de arrays raiz, mejorando compatibilidad con clientes estrictos como Claude Code.
- v1.0.1 agrega recuperacion por sesion persistida: `mem_session_list` lista sesiones recientes, `mem_scope_resolve` prioriza lanes persistidos desde hints explicitos, `mem_bootstrap_context` evita packs project-wide de inicio cuando hay contenedores ambiguos, y `session_id` opcional filtra tools de recuperacion para que proyectos amplios no mezclen chats o agentes. Los packs project-wide que cruzan varias sesiones o sub-scopes inferidos emiten una advertencia visible y recomiendan narrowing antes de tratar el pack como contexto activo. No es conciencia live del turno actual.
- v1.0.1 mantiene las instalaciones normales de continuidad en modo writable; `--read-only` es un modo explicito de auditoria/debug/retrieval-only, no el modo operativo por defecto.

- perfiles MCP de bajo impacto: `minimal`, `standard` y `full`
- modo `--read-only` explicito de auditoria/debug para bloquear tools mutantes y evitar escrituras laterales
- inicializacion lazy de SQLite para conexiones MCP no usadas
- respuestas MCP compactas por defecto, conservando el payload completo en `structuredContent`
- `known_pack_hash` / `not_modified` para no reenviar packs de continuidad sin cambios
- diagnostico runtime con heartbeat, spawn-storm warning, telemetria opcional y daemon/bridge stdio opcional

Releases visibles: [v1.0.2 Identity + Scope Patch](./CHANGELOG.md#102---2026-05-07) | [v1.0.1 Transport + Local Security Hotfix](./CHANGELOG.md#101---prepared-2026-05-06) | [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21)

## Snapshot (fixtures sinteticos v1.0)

| Escenario | Perfil | Tokens fuente | Tokens pack | Ahorro | `not_modified` | Tools | Lazy init | Read-only |
|---|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | `minimal` | 1,841 | 253 | 86.26% | true | 4 | false->true | true |
| Medium agent workflow | `minimal` | 4,855 | 270 | 94.44% | true | 4 | false->true | true |
| Large repeated audit | `minimal` | 9,731 | 269 | 97.24% | true | 4 | false->true | true |
| Sub-agent handoff example | `minimal` | 6,523 | 276 | 95.77% | true | 4 | false->true | true |

En estos fixtures reproducibles, el contexto operativo repetido se redujo de ~22,950 tokens fuente a ~1,068 tokens de pack, una reduccion aproximada de 95.35%. No es una garantia universal; muestra el efecto cuando el agente normalmente reenviaria la misma continuidad del proyecto.

`Tools=4` corresponde al perfil `minimal` previo a session-aware usado en estos fixtures. En v1.0.1, `minimal` tambien incluye `mem_session_list`, `mem_scope_resolve` y `mem_bootstrap_context`, y el perfil `standard` expone 20 tools para recuperacion, gobernanza y auditoria mas amplias.

### Snapshot de runtimes validados

| Runtime | Configuracion | Metricas observadas | Resultado |
|---|---|---|---|
| Default MCP writable | Puentes locales Codex/Gemini/Claude, `read_only=false`; `full` cuando se requieren tools writable | `mem_note_create` escribio notas manuales indexadas y `mem_search` / `mem_context_pack` las recuperaron; `mem_snapshot_create(project_key, label, session_id)` registro proveniencia de alta confianza | Smokes writable de notas manuales y snapshot provenance aprobados |
| Codex Desktop | Codex Desktop, MCP stdio, fixture retrieval-only v1.0 con `minimal`, `read-only`, `compact` | ~22,950 tokens fuente -> ~1,068 tokens de pack, ~95.35% menos contexto repetido, `not_modified=true` en packs repetidos | Validacion MCP de lectura mas verificacion publica reproducible; la continuidad writable se cubre en la fila anterior |
| Codex CLI / `codex exec` | Ruta MCP stdio de Codex CLI, ejecucion corta / efimera | mismo servidor MCP local y estilo de config que Desktop; el lifecycle corto de CLI fue validado por separado del comportamiento del host largo-vivo de Desktop | Ruta Codex CLI validada |
| Google Gemini CLI | MCP stdio `codex-agent-mem`, validacion retrieval-only explicita con `standard`, `read-only`; `compact` si el payload estructurado es visible, si no `verbose` | proceso estable, contador de requests subio como se esperaba, payloads con raiz objeto verificados donde fueron visibles | Validacion MCP de lectura con caveat de exposicion del cliente |
| Claude Code | Claude Opus 4.7, solo MCP stdio `codex-agent-mem`, validacion retrieval-only explicita con `standard`, `read-only`, `compact` | requests `3 -> 8`, lazy init `false -> true`, `same_db_process_count=2` con un host Claude Code activo, `spawn_storm_warning=false`, `mem_search count=2` | Validacion MCP de lectura aprobada |
| Qwen Code | Qwen Code 0.15.0, Ollama local, `qwen3.6:latest`, validacion retrieval-only explicita con `standard`, `read-only`, `compact` | llamadas MCP reales a `mem_context_pack`, `mem_search`, `mem_open_work`, `mem_completion_check`, `mem_health_runtime`; requests `8`, lazy init `true`, `spawn_storm_warning=false`, `not_modified=true` | Validacion MCP local de lectura aprobada |
| Smokes de modelos Qwen locales | Qwen Code 0.15.0 con modelos Ollama `qwen3.6:35b-a3b-q8_0` y `qwen3.5:9b` | ambos modelos respondieron smoke CLI e invocaron `mem_health_runtime` via MCP stdio; retrieval-only `read_only=true`, cierres limpios por `stdin_eof` | Smokes live locales de lectura aprobados |
| DeepSeek-V3.2 | Qwen Code 0.15.0, `deepseek-v3.2:cloud` via Ollama Cloud, validacion retrieval-only explicita con `standard`, `read-only`, `compact` | llamadas MCP reales a `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `spawn_storm_warning=false`, `not_modified=true` | Validacion MCP cloud-backed de lectura aprobada |
| Minimax M2.5 | Qwen Code 0.15.0, `minimax-m2.5:cloud` via Ollama Cloud, validacion retrieval-only explicita con `standard`, `read-only`, `compact` | llamadas MCP reales a `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `not_modified=true` | Validacion MCP cloud-backed de lectura aprobada |
| Kimi Code CLI | Kimi Code CLI 1.38.0, MCP stdio `codex-agent-mem`, validacion retrieval-only explicita con `standard`, `read-only`, `compact` | `kimi mcp test codex-agent-mem` conecto y listo las tools esperadas del perfil standard; la validacion completa con tool-calls de Kimi K2.5 / Kimi K2.6 sigue en evaluacion continua | Conexion MCP de lectura validada; no se afirma validacion del modelo |
| Grok / xAI | Nota de compatibilidad a nivel protocolo | comportamiento MCP stdio / JSON-RPC revisado a nivel protocolo | Nota de protocolo |

Grok / xAI aparece como nota de compatibilidad a nivel protocolo, no como validacion live de tool-calls del modelo. Las filas validadas live son los pares cliente/modelo MCP medidos directamente: Codex Desktop/CLI, Google Gemini CLI, Claude Code, Qwen Code, smokes de modelos Qwen locales, DeepSeek-V3.2 via Ollama Cloud, Minimax M2.5 via Ollama Cloud y validacion de conexion de Kimi Code CLI. En general, `codex-agent-mem` es agnostico al modelo en la capa MCP; se agregan nuevos pares cuando sus mediciones live quedan capturadas.

## Resultados verificables

`codex-agent-mem` incluye un sandbox reproducible de verificacion y un export publico de evidencia para v1.0.0. El uso de fixtures reproducibles es intencional: el MCP busca optimizar el manejo repetible del contexto operativo, por eso la evidencia publica mantiene controlado ese contexto repetido en vez de convertir cada corrida en una conversacion distinta.

La evidencia publica v1.0.x combina fixtures reproducibles de verificacion con validacion MCP live en los runtimes listados arriba. Mide compresion de contexto, evitacion de reenvio con `known_pack_hash`, inicializacion lazy, perfil minimo de tools, seguridad del modo read-only explicito, response diet, telemetria local, control de cierre y un ejemplo con sub-agentes.

Ver: [Verification Evidence](./docs/verification/) y [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md).

## Claude Code y claude-mem

`codex-agent-mem` funciona en Claude Code como servidor MCP stdio estandar. No instala hooks de inicio de sesion, hooks de cierre ni resumen automatico post-turno. La memoria se recupera bajo demanda con tools MCP como `mem_context_pack`, `mem_search`, `mem_open_work` y `mem_completion_check`.

Si ya usas `claude-mem`, ambas herramientas pueden coexistir tecnicamente. Para flujos de menor overhead y menor latencia, conviene usar una sola capa de memoria activa a la vez. En validacion local con un host Claude Code activo, `codex-agent-mem` solo mantuvo el runtime compacto (`same_db_process_count=2`, `spawn_storm_warning=false`). Al correrlo junto a `claude-mem`, la superficie visible subio a 61 tools, se agrego un bloque de inicio de sesion de unos 6,995 tokens y aparecieron demoras post-turno por stop hooks. Esto no rompe `codex-agent-mem`, pero hace mas dificil comparar resultados y puede aumentar overhead y latencia.

Usa `codex-agent-mem` si prefieres memoria local-first, auditable, pull-based, con recuperacion explicita y cierre determinista. Usa plugins de memoria adicionales solo cuando busques intencionalmente su comportamiento automatico basado en hooks.

Para flujos Claude Code sensibles a tokens, `codex-agent-mem` esta pensado para operar con bajo overhead por defecto: sin inyeccion al inicio de sesion, sin resumen por stop hook, respuestas compactas, presupuestos explicitos y atajo `pack_hash` / `not_modified` cuando el pack no cambio.

## Complemento opcional: clean-process-ended

`codex-agent-mem` v1.0.1 y `clean-process-ended` ([GitHub](https://github.com/MarceloCaporale/clean-process-ended)) v0.7.2 funcionan de forma independiente, pero resuelven problemas vecinos en flujos locales con agentes.

- `codex-agent-mem` preserva continuidad: memoria de proyecto, packs de contexto acotados, notas manuales, snapshots, trabajo abierto, blockers y chequeos deterministas de cierre.
- `clean-process-ended` cubre higiene de procesos locales: diagnostico ownership-first, chequeos de cierre en dry-run y recibos compactos de janitor.

Juntos mejoran los cierres de tarea: recuperar contexto, terminar el trabajo, revisar estado local de procesos y guardar evidencia compacta de cierre sin convertir ninguno de los dos MCP en dependencia obligatoria del otro.

## Lo que ofrece

### Continuidad

- **Continuidad compacta**: convierte contexto repetido en packs mas chicos para `AGENTS.md` solo cuando realmente conviene
- **Estado operativo persistente entre sesiones y agentes**: mantiene objetivo, restricciones, pendientes, blockers, Definition of Done y guardarrailes de alcance para que el contexto no quede rehen de una sola plataforma, una sola sesion o un solo modelo
- **Integracion MCP-nativa**: corre como servidor MCP stdio local para Codex, Claude Code, Google Gemini CLI, Qwen Code y otros clientes compatibles con MCP; `notify` de Codex y la sincronizacion opcional de `AGENTS.md` siguen disponibles cuando aportan valor
- **Economia de tokens para flujos con agentes**: mejora el uso de tokens en trabajo repetido con agentes al reducir replay de continuidad cuando gana el pack compacto; los fixtures publicos de v1.0 muestran reducciones de 86% a 97% en escenarios de contexto repetido

### Control de cierre

- **Control de cierre determinista**: `mem_open_work` y `mem_completion_check` hacen que el trabajo abierto pese mas que un viejo “done”
- **Retencion de alcance**: arrastra recent changes, must-not-drop, blockers y continuidad activa, no solo decisiones

### Gobernanza y auditoria

- **Seleccion gobernada de memoria**: aplica policies, inheritance y repairs en vez de mezclar memoria sin criterio
- **Memoria MCP inspeccionable**: la UI local `/ui` permite navegar cambios recientes, scope guard, provenance, health, snapshots, estado de gobernanza y memoria almacenada sin abrir la base SQLite a mano
- **Todo local y auditable**: SQLite + FTS5, provenance, health, snapshots y UI local, sin servicio externo de memoria ni sincronizacion saliente de memoria
- **Frontera local de seguridad clara**: v1.0.1 endurece acceso loopback al daemon, bearer token opcional, `/health` sanitizado y jerarquia de instrucciones del contexto generado; no es una proteccion completa contra prompt injection, y la base SQLite publica 1.0.x sigue en texto plano por defecto y no debe usarse como vault de secretos

Docs clave: [AGENTS.md](./AGENTS.md) | [Quickstart](./docs/quickstart.md) | [Integracion Codex](./docs/codex-integration.md) | [Nota Codex Desktop](./docs/codex-desktop-lifecycle-note.md) | [Support Matrix](./docs/support-matrix.md) | [Design Decisions](./docs/design-decisions.md)

Sirve para auditorias largas, continuidad de proyectos complejos y sesiones donde el problema no es solo recordar decisiones, sino no perder alcance ni dar por terminado algo que sigue abierto.

## Estado

`1.0.2` es la release actual de mantenimiento 1.0.x. `1.0.0` sigue siendo la base publica de verificacion para las metricas reproducibles de abajo.

Hoy funciona:

- ingesta de `notify` de Codex sobre `agent-turn-complete`
- persistencia local en SQLite con FTS5
- extraccion heuristica de `session_summary`, `decision`, `objective`, `constraint`, `pending_item`, `completed_item`, `blocker` y `completion_claim`
- Definition of Done jerarquica en `project_dod`, `mission_dod` y `session_dod`
- generacion de packs compactos de continuidad con estimacion aproximada de tokens
- presupuestos de pack `micro`, `normal` y `full`
- sincronizacion opcional de `AGENTS.md` con `--sync-project-doc` cuando el pack es realmente mas chico que el contexto fuente
- arrastre de estado operativo para recuperar objetivo, pendientes, blockers y guardarrailes de alcance en la siguiente sesion
- control de cierre determinista con `mem_open_work` y `mem_completion_check`
- deltas de cambios recientes con `mem_recent_changes`
- continuidad de alcance y guardarrailes de “no perder” con `mem_scope_guard`
- guardarrail contra cierre falso cuando todavia quedan pendientes, blockers o gaps de DoD
- metricas persistidas de cierre y compresion por proyecto
- seleccion automatica de presupuesto de pack cuando `budget=auto`
- provenance de memoria persistida por observacion y consultable con `mem_provenance`
- diagnostico de salud del proyecto con `mem_health`
- diagnostico runtime del servidor MCP con `mem_health_runtime`
- notas operativas manuales con `mem_note_create`, indexadas para `mem_search` y elegibles para `mem_context_pack`
- snapshots versionados del proyecto con `mem_snapshot_create`, `mem_snapshot_list` y `mem_snapshot_restore`
- policies de memoria gobernada con `mem_policy_validate`, `mem_policy_add`, `mem_policy_list` y `mem_policy_remove`
- inheritance selectiva entre proyectos con `mem_inheritance_add`, `mem_inheritance_list` y `mem_inheritance_remove`
- propuestas de repair y repairs derivados con `mem_repair_propose` y `mem_repair_apply`
- perfiles MCP de bajo impacto con `--profile minimal|standard|full`
- modo MCP read-only explicito de auditoria/debug con `--read-only`
- texto MCP compacto con `structuredContent` completo
- reutilizacion de packs de continuidad con `known_pack_hash` / `not_modified`
- cache in-process corto para tools de lectura costosas
- inicializacion lazy de SQLite para conexiones MCP baratas no usadas
- runtime health enriquecido con perfil, mutabilidad, cache, lazy init, heartbeat y diagnostico spawn-storm
- telemetria runtime local opcional con `--telemetry-mode off|summary|debug`
- daemon local opcional con `codex-agent-mem-daemon` y modo bridge stdio con `--daemon-url`
- API de inspeccion con FastAPI
- UI local de inspeccion en `/ui`, incluyendo cambios recientes, scope guard, provenance, health, snapshots y estado de gobernanza
- CLI local de policies con `codex-agent-mem-policy`
- servidor MCP por stdio con:
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
- tests automatizados

Lo que todavia queda fuera de alcance a proposito:

- embeddings
- vector stores
- ingesta desde Codex App Server
- adaptador de hooks de Codex
- adaptador para Ollama
- orquestacion multiagente

## Por que existe este repositorio

- Los flujos con agentes suelen necesitar contexto duradero fuera de un unico proceso runtime.
- La recuperacion por si sola no resuelve el fallo mayor: perder alcance y obligar al usuario a repetir contexto previo.
- Un bloque compacto de continuidad o un context pack MCP puede reducir cuanto contexto anterior hay que repetir manualmente.
- Guardar solo decisiones no alcanza; el runtime tambien necesita objetivo activo, trabajo abierto, blockers y una regla contra el cierre falso.
- SQLite mantiene la implementacion local-first, auditable y facil de inspeccionar.
- La release actual se enfoca a proposito en un slice estrecho y verificable, no en una plataforma amplia sin terminar.
- Hosts MCP largos y cortos pueden comportarse distinto bajo carga; los docs de validacion definen el limite exacto.

## Modelo de instalacion

`codex-agent-mem` se instala como paquete Python local y se expone a clientes compatibles con MCP mediante comandos stdio.

El patron estable es:

1. instalar el paquete
2. apuntar el cliente MCP al comando instalado
3. mantener la base de memoria local y auditable

Los snippets especificos de Codex para `notify` y `mcp_servers` los genera `codex-agent-mem-bootstrap-codex`; otros clientes MCP usan sus propios archivos de configuracion.

## Quickstart

Si quieres el camino mas corto desde clone hasta un setup local funcional:

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

En Codex, pega el snippet generado en `~/.codex/config.toml`. En otros clientes MCP, usa el comando stdio comun de [Configurar clientes MCP](#configurar-clientes-mcp).

## Instalacion

### Opcion A: `pipx` desde GitHub

Instala directo desde la URL del repositorio:

```bash
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

### Opcion B: instalacion local de desarrollo

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

## Configurar clientes MCP

El punto de entrada del servidor MCP es el mismo para cualquier cliente compatible:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Apunta tu cliente compatible con MCP a ese comando stdio instalado. Las rutas publicas validadas en v1.0.x incluyen Codex CLI/Desktop, Claude Code, Google Gemini CLI, Qwen Code con modelos Qwen locales via Ollama, DeepSeek-V3.2 y Minimax M2.5 via Ollama Cloud, ademas de validacion de conexion en Kimi Code CLI.

### Helper para Codex

Genera un snippet listo para pegar:

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Para Codex, eso imprime el bloque `notify`, el bloque `[mcp_servers."codex-agent-mem"]`, un idle timeout explicito para stdio y las aprobaciones de las tools MCP para pegar en `~/.codex/config.toml`.

Para sesiones largas de Codex Desktop, prefiere un MCP idle timeout mas largo, por ejemplo `--idle-timeout-seconds 1800`, para reducir la probabilidad de que el thread de Desktop conserve un transporte stdio cerrado. Para corridas CLI cortas o `codex exec`, `300` segundos suele ser suficiente y limpia mas rapido.

Si tambien quieres reinyeccion automatica en `AGENTS.md`, agrega `--sync-project-doc` al comando `notify`.

## Como debe usarlo el agente

Una vez configurado, el agente debe usar `codex-agent-mem` de forma proactiva cuando la continuidad importa. No deberias tener que repetir "usa el MCP de memoria" cada pocos turnos.

Patron recomendado:

- empezar con `mem_bootstrap_context` cuando puedan importar decisiones previas, trabajo pendiente, blockers, restricciones o estado del proyecto; pasar titulo de chat, thread, cwd o repo cuando el host lo exponga
- llamar `mem_context_pack` directamente solo cuando el alcance ya sea explicito, idealmente con `session_id` en workspaces amplios
- pasar `known_pack_hash` en chequeos repetidos para que los packs sin cambios devuelvan `not_modified` en vez de reenviar contexto
- usar `mem_search` solo cuando el pack compacto no alcance
- antes de decir que algo esta terminado, llamar `mem_open_work` y `mem_completion_check` en tareas de implementacion, validacion, publicacion, migracion o documentacion

De ahi sale la economia practica de tokens: continuidad compacta primero, expansion puntual solo cuando hace falta, y no reenviar el mismo pack si nada cambio.

Tambien hay ejemplos en [examples/codex](./examples/codex/) y notas de flujos via Ollama en [examples/ollama](./examples/ollama/).

## Ejecucion local

Levanta la API de inspeccion:

```bash
codex-agent-mem-api --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Luego abre:

```text
http://127.0.0.1:37770/ui
```

Levanta el servidor MCP:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

El transporte MCP actual es stdio. Eso significa que un proceso por conexion del host es normal; no es un daemon singleton. El idle timeout defensivo permite que instancias no usadas o huerfanas salgan limpiamente.

Defaults recomendados: usa un timeout mas largo para sesiones Codex Desktop, por ejemplo `1800` segundos, y uno mas corto para ejecuciones CLI/efimeras, por ejemplo `300` segundos.

Reconstruye manualmente el bloque de continuidad generado para un directorio:

```bash
codex-agent-mem-refresh-context --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db" --project-key YOUR_PROJECT --cwd /path/to/project
```

```powershell
codex-agent-mem-refresh-context --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --project-key YOUR_PROJECT --cwd C:\Path\To\Project
```

## Verificacion rapida

Corre el smoke test:

```bash
codex-agent-mem-smoke --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Eso inserta un turno de ejemplo, extrae observaciones y verifica recuperacion reciente y generacion de `project_brief`.

## Economia de tokens: que ahorra tokens hoy

- El paquete compila un pack de working memory mas chico a partir de turnos recientes, decisiones duraderas y estado operativo derivado.
- Cuando `--sync-project-doc` esta activo y ese pack es realmente mas chico que el contexto fuente, se sincroniza en `AGENTS.md` para el directorio de trabajo.
- La recuperacion MCP y la sincronizacion opcional de `AGENTS.md` permiten iniciar sesiones futuras con continuidad comprimida en vez de obligarte a repetir el alcance viejo.
- `mem_context_pack` expone el mismo pack compacto por MCP para recuperacion bajo demanda.
- El pack arrastra pendientes y blockers, asi una ejecucion futura puede recuperar "que falta" y no solo "que se decidio".

Esto es economia de tokens para flujos con agentes, no compresion magica. `codex-agent-mem` mejora la economia de contexto al reducir contexto repetido de proyecto, reutilizar packs sin cambios con `known_pack_hash` y permitir que el agente expanda solo la memoria que necesita.

## Ahorro aproximado de tokens

En lenguaje simple: esto busca reducir la cantidad de contexto repetido que hay que volver a pasarle al agente. No lo elimina por completo, pero si puede recortarlo de forma util.

Lo que hoy podemos decir honestamente a partir de validaciones locales:

- los fixtures publicos de v1.0 redujeron contexto repetido de ~22,950 tokens fuente a ~1,068 tokens de pack, cerca de `95.35%` en ese escenario controlado
- los escenarios individuales del sandbox quedaron entre `86%` y `97%` de reduccion
- las validaciones live confirmaron recuperacion MCP compacta, proceso estable, comportamiento de raiz objeto/no-reinyeccion donde fue visible y snapshot provenance writable en los puentes locales Codex/Gemini/Claude

Ejemplos del sandbox publico v1.0:

- `1,841 -> 253` tokens aproximados
- `4,855 -> 270` tokens aproximados
- `9,731 -> 269` tokens aproximados
- `6,523 -> 276` tokens aproximados

Importante: no es una garantia fija por prompt. Si el pack generado no es realmente mas chico que el contexto fuente, `codex-agent-mem` no lo reinyecta y evita fingir un ahorro que no existe.

## Que ayuda a detectar hoy

- perder el objetivo original despues de algunas corridas
- achicar el alcance en silencio cuando el usuario pidio mas
- declarar terminado mientras todavia hay trabajo pendiente
- olvidar blockers y volver a entrar en la siguiente ejecucion como si la tarea ya estuviera cerrada

## Estructura del repositorio

- [src/codex_agent_mem](./src/codex_agent_mem/) - codigo del paquete
- [tests](./tests/) - tests ejecutables
- [examples/codex](./examples/codex/) - ejemplos de integracion con Codex
- [examples/ollama](./examples/ollama/) - notas para flujos via Ollama
- [scripts](./scripts/) - helpers de bootstrap local
- [docs](./docs/) - arquitectura y notas de release

## Mapa de documentacion

- [AGENTS.md](./AGENTS.md) - mapa del repo y guia operativa para agentes de IA compatibles con MCP
- [docs/quickstart.md](./docs/quickstart.md) - camino mas corto de instalacion y primera ejecucion
- [docs/codex-integration.md](./docs/codex-integration.md) - como encajan notify y MCP en Codex
- [docs/verification](./docs/verification/) - metricas publicas reproducibles y evidencia v1.0.0
- [docs/support-matrix.md](./docs/support-matrix.md) - soporte actual y gaps conocidos
- [docs/codex-desktop-lifecycle-note.md](./docs/codex-desktop-lifecycle-note.md) - comportamiento observado de Codex Desktop y mitigaciones practicas
- [docs/design-decisions.md](./docs/design-decisions.md) - decisiones explicitas de producto y arquitectura
- [docs/architecture.md](./docs/architecture.md) - arquitectura tecnica portable de la release actual
- [docs/validation](./docs/validation/) - niveles de validacion, soporte runtime, comportamiento de clientes y notas publicas de evidencia
- [CONTRIBUTING.md](./CONTRIBUTING.md) - flujo de contribucion y barra de calidad
- [SECURITY.md](./SECURITY.md) - alcance de soporte y guia de reporte de seguridad
- [docs/discoverability.md](./docs/discoverability.md) - descripcion GitHub, topics y framing de release sugeridos

## Superficie de release

Este repositorio incluye:

- layout limpio en la raiz
- `pyproject.toml` instalable
- entry points de comandos
- tests
- workflow de CI
- licencia
- changelog

## Autor

Creado y mantenido por Marcelo Caporale.

- X: [@MarceloCaporale](https://x.com/MarceloCaporale)
- Estudio: [Visual AI Media](https://visualaimedia.com)
- Lab: [Visual Systems Lab](https://visualsystemslab.com)
