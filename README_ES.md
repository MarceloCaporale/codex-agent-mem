# codex-agent-mem

Otros idiomas: [English](./README.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Memoria portable, auditable y local-first para Codex y flujos con agentes de programacion.

codex-agent-mem conserva memoria duradera fuera del runtime del modelo, comprime continuidad en packs mas chicos, y arrastra estado operativo para que Codex retome con menos repeticion, menos cierres falsos y mas control sobre lo que entra en contexto.

Todo se guarda y procesa localmente en este MCP: base SQLite, indice FTS, snapshots, metadata de telemetria y UI opcional de inspeccion. `codex-agent-mem` no envia tu memoria, datos del proyecto, prompts ni telemetria a ningun servidor externo.

`codex-agent-mem` nacio para Codex y flujos GPT-5.x, pero evoluciono como una capa portable de memoria MCP para runtimes compatibles con MCP como Codex CLI, Codex Desktop, Gemini CLI con Gemini 3.1 Pro, Claude Code con Opus 4.7 o Sonnet 4.6, Qwen Code con modelos locales Qwen 3.6 / Qwen 3.5 via Ollama, DeepSeek-V3.2 y Minimax M2.5 via Ollama Cloud, y agentes locales personalizados. En evaluacion continua: Kimi Code CLI, GLM-5, Kimi K2.5 y Kimi K2.6. Kimi Code CLI conecta con el servidor MCP `codex-agent-mem` via stdio; la validacion live completa con tool-calls del modelo se mide por separado antes de publicarse como validada. Tambien fue auditado externamente a nivel de protocolo para compatibilidad con Grok / xAI y orquestadores MCP tipo DeepSeek. Vive en local, mantiene la memoria auditable y bajo demanda, y no envia tu memoria almacenada a ningun servicio externo.

Baseline publica. Construida en slices chicos y verificables, todavia en evolucion, pero ya pensada para uso real.

## Novedades de v1.0.0

- perfiles MCP de bajo impacto: `minimal`, `standard` y `full`
- modo `--read-only` real para bloquear tools mutantes y evitar escrituras laterales
- inicializacion lazy de SQLite para conexiones MCP no usadas
- respuestas MCP compactas por defecto, conservando el payload completo en `structuredContent`
- `known_pack_hash` / `not_modified` para no reenviar packs de continuidad sin cambios
- diagnostico runtime con heartbeat, spawn-storm warning, telemetria opcional y daemon/bridge stdio opcional

Releases visibles: [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Snapshot (fixtures sinteticos v1.0)

| Escenario | Perfil | Tokens fuente | Tokens pack | Ahorro | `not_modified` | Tools | Lazy init | Read-only |
|---|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | `minimal` | 1,841 | 216 | 88.27% | true | 4 | false->true | true |
| Medium agent workflow | `minimal` | 4,855 | 233 | 95.20% | true | 4 | false->true | true |
| Large repeated audit | `minimal` | 9,731 | 232 | 97.62% | true | 4 | false->true | true |
| Sub-agent handoff example | `minimal` | 6,523 | 239 | 96.34% | true | 4 | false->true | true |

En estos fixtures reproducibles, el contexto operativo repetido se redujo de ~22,950 tokens fuente a ~920 tokens de pack, una reduccion aproximada de 96.0%. No es una garantia universal; muestra el efecto cuando el agente normalmente reenviaria la misma continuidad del proyecto.

`Tools=4` corresponde al perfil `minimal` usado en estos fixtures. El perfil `standard` expone 17 tools para recuperacion, gobernanza y auditoria mas amplias.

### Snapshot de runtimes validados

| Runtime | Configuracion | Metricas observadas | Resultado |
|---|---|---|---|
| Codex Desktop | GPT-5.4, razonamiento xhigh, fixtures sinteticos v1.0 | ~22,950 tokens fuente -> ~920 tokens de pack, ~96.0% menos contexto repetido, `not_modified=true` en packs repetidos | Verificacion publica reproducible |
| Gemini CLI | Gemini 3.1 Pro, MCP stdio `codex-agent-mem`, `standard`, `read-only`, `compact` | proceso estable, contador de requests subio como se esperaba, `mem_search` devolvio raiz objeto `{items, count}` con `count=2` | Validacion live aprobada |
| Claude Code | Claude Opus 4.7, solo MCP stdio `codex-agent-mem`, `standard`, `read-only`, `compact` | requests `3 -> 8`, lazy init `false -> true`, `same_db_process_count=2` con un host Claude Code activo, `spawn_storm_warning=false`, `mem_search count=2` | Validacion live aprobada |
| Qwen Code | Qwen Code 0.15.0, Ollama local, `qwen3.6:latest`, `standard`, `read-only`, `compact` | llamadas MCP reales a `mem_context_pack`, `mem_search`, `mem_open_work`, `mem_completion_check`, `mem_health_runtime`; requests `8`, lazy init `true`, `spawn_storm_warning=false`, `not_modified=true` | Validacion live local aprobada |
| Smokes de modelos Qwen locales | Qwen Code 0.15.0 con modelos Ollama `qwen3.6:35b-a3b-q8_0` y `qwen3.5:9b` | ambos modelos respondieron smoke CLI e invocaron `mem_health_runtime` via MCP stdio; requests `4`, `read_only=true`, cierres limpios por `stdin_eof` | Smokes live locales aprobados |
| DeepSeek-V3.2 | Qwen Code 0.15.0, `deepseek-v3.2:cloud` via Ollama Cloud, `standard`, `read-only`, `compact` | llamadas MCP reales a `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `spawn_storm_warning=false`, `not_modified=true` | Validacion MCP live cloud-backed aprobada |
| Minimax M2.5 | Qwen Code 0.15.0, `minimax-m2.5:cloud` via Ollama Cloud, `standard`, `read-only`, `compact` | llamadas MCP reales a `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `not_modified=true` | Validacion MCP live cloud-backed aprobada |
| Kimi Code CLI | Kimi Code CLI 1.38.0, MCP stdio `codex-agent-mem`, `standard`, `read-only`, `compact` | `kimi mcp test codex-agent-mem` conecto y listo 17 tools; la validacion completa con tool-calls de Kimi K2.5 / Kimi K2.6 sigue en evaluacion continua | Conexion MCP validada; no se afirma validacion del modelo |
| Grok / xAI | Auditoria externa de modelo/runtime; no hay Grok CLI local disponible | compatible por protocolo mediante un orquestador MCP stdio o un wrapper JSON-RPC stdio fino | Auditado externamente; no validado live local |

Grok es auditoria externa, no una sesion CLI live local en esta maquina. Qwen Code ya fue validado localmente con modelos Ollama y MCP stdio. DeepSeek-V3.2 y Minimax M2.5 fueron validados live con modelos cloud-backed de Ollama, no con inferencia local. Kimi Code CLI ya quedo conectado al MCP, mientras que la validacion a nivel modelo con Kimi K2.5 / Kimi K2.6 sigue como evaluacion continua porque los modelos completos requieren una via runtime separada. En general, `codex-agent-mem` es agnostico al modelo en la capa MCP; la tabla lista los pares modelo/runtime ya medidos en vivo, y se agregan nuevos pares a medida que se capturan sus mediciones live. Para hosts sin cliente MCP nativo, la via esperada es un wrapper fino JSON-RPC stdio o un orquestador compatible con MCP.

## Resultados verificables

`codex-agent-mem` incluye un sandbox reproducible de verificacion y un export publico de evidencia para v1.0.0.

La corrida publica actual fue ejecutada con **Codex Desktop, modelo GPT-5.4, razonamiento xhigh** sobre fixtures sinteticos. Mide compresion de contexto, evitacion de reenvio con `known_pack_hash`, inicializacion lazy, perfil minimo de tools, seguridad read-only, response diet, telemetria local, control de cierre y un ejemplo con sub-agentes.

Ver: [Verification Evidence](./docs/verification/) y [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md).

## Claude Code y claude-mem

`codex-agent-mem` funciona en Claude Code como servidor MCP stdio estandar. No instala hooks de inicio de sesion, hooks de cierre ni resumen automatico post-turno. La memoria se recupera bajo demanda con tools MCP como `mem_context_pack`, `mem_search`, `mem_open_work` y `mem_completion_check`.

Si ya usas `claude-mem`, ambas herramientas pueden coexistir tecnicamente. Para flujos de menor overhead y menor latencia, conviene usar una sola capa de memoria activa a la vez. En validacion local con un host Claude Code activo, `codex-agent-mem` solo mantuvo el runtime compacto (`same_db_process_count=2`, `spawn_storm_warning=false`). Al correrlo junto a `claude-mem`, la superficie visible subio a 61 tools, se agrego un bloque de inicio de sesion de unos 6,995 tokens y aparecieron demoras post-turno por stop hooks. Esto no rompe `codex-agent-mem`, pero hace mas dificil comparar resultados y puede aumentar overhead y latencia.

Usa `codex-agent-mem` si prefieres memoria local-first, auditable, pull-based, con recuperacion explicita y cierre determinista. Usa plugins de memoria adicionales solo cuando busques intencionalmente su comportamiento automatico basado en hooks.

Para flujos Claude Code sensibles a tokens, `codex-agent-mem` esta pensado para ser barato por defecto: sin inyeccion al inicio de sesion, sin resumen por stop hook, respuestas compactas, presupuestos explicitos y atajo `pack_hash` / `not_modified` cuando el pack no cambio.

## Lo que ofrece

### Continuidad

- **Continuidad compacta**: convierte contexto repetido en packs mas chicos para `AGENTS.md` solo cuando realmente conviene
- **Estado operativo persistente**: mantiene objetivo, restricciones, pendientes, blockers, Definition of Done y guardarrailes de alcance
- **Integracion nativa con Codex**: pensado para `notify`, MCP stdio, sincronizacion opcional de `AGENTS.md` y cierre defensivo del runtime
- **Ahorro practico de tokens**: reduce repeticion de continuidad cuando gana el pack compacto; los fixtures publicos de v1.0 muestran reducciones de 88% a 97% en escenarios de contexto repetido

### Control de cierre

- **Control de cierre determinista**: `mem_open_work` y `mem_completion_check` hacen que el trabajo abierto pese mas que un viejo “done”
- **Retencion de alcance**: arrastra recent changes, must-not-drop, blockers y continuidad activa, no solo decisiones

### Gobernanza y auditoria

- **Seleccion gobernada de memoria**: aplica policies, inheritance y repairs en vez de mezclar memoria sin criterio
- **Todo local y auditable**: SQLite + FTS5, provenance, health, snapshots y UI local, sin servicio externo de memoria ni sincronizacion saliente de memoria

Sirve para auditorias largas, continuidad de proyectos complejos y sesiones donde el problema no es solo recordar decisiones, sino no perder alcance ni dar por terminado algo que sigue abierto.

## Estado

`1.0.0` es la release base actual.

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
- snapshots versionados del proyecto con `mem_snapshot_create`, `mem_snapshot_list` y `mem_snapshot_restore`
- policies de memoria gobernada con `mem_policy_validate`, `mem_policy_add`, `mem_policy_list` y `mem_policy_remove`
- inheritance selectiva entre proyectos con `mem_inheritance_add`, `mem_inheritance_list` y `mem_inheritance_remove`
- propuestas de repair y repairs derivados con `mem_repair_propose` y `mem_repair_apply`
- API de inspeccion con FastAPI
- UI local de inspeccion en `/ui`, incluyendo cambios recientes, scope guard, provenance, health, snapshots y estado de gobernanza
- CLI local de policies con `codex-agent-mem-policy`
- servidor MCP por stdio con:
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
- tests automatizados

Lo que todavia queda fuera de alcance a proposito:

- embeddings
- vector stores
- ingesta desde Codex App Server
- adaptador de hooks de Codex
- adaptador para Ollama
- orquestacion multiagente

## Expectativa importante

Codex hoy no instala herramientas MCP arbitrarias desde una URL de GitHub en un solo paso.

El camino soportado sigue siendo:

1. instalar el paquete Python
2. apuntar `notify` y `mcp_servers` de Codex a los comandos instalados

Este repositorio esta preparado para que ese flujo sea limpio y repetible.

## Instalacion

### Opcion A: `pipx` desde GitHub

Instala directo desde la URL del repositorio:

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### Opcion B: instalacion local de desarrollo

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

## Configurar Codex

Genera un snippet listo para pegar:

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Eso imprime el bloque `notify`, el bloque `[mcp_servers."codex-agent-mem"]`, un idle timeout explicito para stdio y las aprobaciones read-only de las tools MCP para pegar en `~/.codex/config.toml`.

Si tambien quieres reinyeccion automatica en `AGENTS.md`, agrega `--sync-project-doc` al comando `notify`.

## Como debe usarlo el agente

Una vez configurado, el agente debe usar `codex-agent-mem` de forma proactiva cuando la continuidad importa. No deberias tener que repetir "usa el MCP de memoria" cada pocos turnos.

Patron recomendado:

- empezar con `mem_context_pack` cuando puedan importar decisiones previas, trabajo pendiente, blockers, restricciones o estado del proyecto
- pasar `known_pack_hash` en chequeos repetidos para que los packs sin cambios devuelvan `not_modified` en vez de reenviar contexto
- usar `mem_search` solo cuando el pack compacto no alcance
- antes de decir que algo esta terminado, llamar `mem_open_work` y `mem_completion_check` en tareas de implementacion, validacion, publicacion, migracion o documentacion

De ahi sale el ahorro practico de tokens: continuidad compacta primero, expansion puntual solo cuando hace falta, y no reenviar el mismo pack si nada cambio.

Tambien hay ejemplos en [examples/codex](./examples/codex/).

## Ejecucion local

Levanta la API de inspeccion:

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Luego abre:

```text
http://127.0.0.1:37770/ui
```

Levanta el servidor MCP:

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

## Verificacion rapida

Corre el smoke test:

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Eso inserta un turno de ejemplo, extrae observaciones y verifica recuperacion reciente y generacion de `project_brief`.

## Ahorro aproximado de tokens

En lenguaje simple: esto busca reducir la cantidad de contexto repetido que hay que volver a pasarle a Codex. No lo elimina por completo, pero si puede recortarlo de forma util.

Lo que hoy podemos decir honestamente a partir de validaciones locales:

- los fixtures publicos de v1.0 redujeron contexto repetido de ~22,950 tokens fuente a ~920 tokens de pack, cerca de `96.0%` en ese escenario controlado
- los escenarios individuales del sandbox quedaron entre `88%` y `97%` de reduccion
- las validaciones live en Gemini CLI, Claude Code, Qwen Code, DeepSeek-V3.2 via Ollama Cloud y Minimax M2.5 via Ollama Cloud confirmaron recuperacion MCP compacta, proceso estable, modo read-only y comportamiento de raiz objeto/no-reinyeccion donde fue visible

Ejemplos del sandbox publico v1.0:

- `1,841 -> 216` tokens aproximados
- `4,855 -> 233` tokens aproximados
- `9,731 -> 232` tokens aproximados
- `6,523 -> 239` tokens aproximados

Importante: no es una garantia fija por prompt. Si el pack generado no es realmente mas chico que el contexto fuente, `codex-agent-mem` no lo reinyecta y evita fingir un ahorro que no existe.

## Estructura del repositorio

- [src/codex_agent_mem](./src/codex_agent_mem/) - codigo del paquete
- [tests](./tests/) - tests ejecutables
- [examples/codex](./examples/codex/) - ejemplos de integracion con Codex
- [scripts](./scripts/) - helpers de bootstrap local
- [docs](./docs/) - arquitectura y notas de release

## Superficie de release

Este repositorio incluye:

- layout limpio en la raiz
- `pyproject.toml` instalable
- entry points de comandos
- tests
- workflow de CI
- licencia
- changelog
