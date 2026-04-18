# codex-agent-mem

Otros idiomas: [English](./README.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Memoria portable, auditable y local-first para Codex y flujos con agentes de programacion.

codex-agent-mem conserva memoria duradera fuera del runtime del modelo, comprime continuidad en packs mas chicos, y arrastra estado operativo para que Codex retome con menos repeticion, menos cierres falsos y mas control sobre lo que entra en contexto.

Release `alpha`. Iteracion rapida, slices chicos y baselines publicas en secuencia.

## Novedades de v0.9.0

- policies de memoria para inclusion y exclusion explicita
- inheritance selectiva entre proyectos sin mezclar continuidad a ciegas
- propuestas de repair y repairs derivados desde health
- visibilidad de gobernanza en la UI local y en la documentacion

Releases visibles: [v0.9.0 Governance](./CHANGELOG.md#090---2026-04-18) | [v0.8.0 Persistence & Observability](./CHANGELOG.md#080---2026-04-18)

## Lo que ofrece

### Continuidad

- **Continuidad compacta**: convierte contexto repetido en packs mas chicos para `AGENTS.md` solo cuando realmente conviene
- **Estado operativo persistente**: mantiene objetivo, restricciones, pendientes, blockers, Definition of Done y guardarrailes de alcance
- **Integracion nativa con Codex**: pensado para `notify`, MCP stdio y sincronizacion automatica de `AGENTS.md`
- **Ahorro practico de tokens**: suele reducir entre `20%` y `55%` del contexto repetido cuando gana el pack compacto

### Control de cierre

- **Control de cierre determinista**: `mem_open_work` y `mem_completion_check` hacen que el trabajo abierto pese mas que un viejo “done”
- **Retencion de alcance**: arrastra recent changes, must-not-drop, blockers y continuidad activa, no solo decisiones

### Gobernanza y auditoria

- **Seleccion gobernada de memoria**: aplica policies, inheritance y repairs en vez de mezclar memoria sin criterio
- **Todo local y auditable**: SQLite + FTS5, provenance, health, snapshots y UI local, sin servicio externo de memoria

Sirve para auditorias largas, continuidad de proyectos complejos y sesiones donde el problema no es solo recordar decisiones, sino no perder alcance ni dar por terminado algo que sigue abierto.

## Estado

`0.9.0` es la release base actual.

Hoy funciona:

- ingesta de `notify` de Codex sobre `agent-turn-complete`
- persistencia local en SQLite con FTS5
- extraccion heuristica de `session_summary`, `decision`, `objective`, `constraint`, `pending_item`, `completed_item`, `blocker` y `completion_claim`
- Definition of Done jerarquica en `project_dod`, `mission_dod` y `session_dod`
- generacion de packs compactos de continuidad con estimacion aproximada de tokens
- presupuestos de pack `micro`, `normal` y `full`
- sincronizacion automatica de `AGENTS.md` cuando el pack es realmente mas chico que el contexto fuente
- arrastre de estado operativo para recuperar objetivo, pendientes, blockers y guardarrailes de alcance en la siguiente sesion
- control de cierre determinista con `mem_open_work` y `mem_completion_check`
- deltas de cambios recientes con `mem_recent_changes`
- continuidad de alcance y guardarrailes de “no perder” con `mem_scope_guard`
- guardarrail contra cierre falso cuando todavia quedan pendientes, blockers o gaps de DoD
- metricas persistidas de cierre y compresion por proyecto
- seleccion automatica de presupuesto de pack cuando `budget=auto`
- provenance de memoria persistida por observacion y consultable con `mem_provenance`
- diagnostico de salud del proyecto con `mem_health`
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

Eso imprime el bloque `notify`, el bloque `[mcp_servers."codex-agent-mem"]` y las aprobaciones read-only de las tools MCP para pegar en `~/.codex/config.toml`.

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

- en casos favorables, el pack compacto redujo el contexto repetido entre `20%` y `55%`
- en muchas corridas reales, el ahorro quedo entre `un tercio` y `la mitad` menos de contexto repetido
- si un flujo iba a necesitar volver a pasar aproximadamente `1000` tokens de contexto previo, una expectativa razonable suele ser algo mas parecido a `450` a `800` tokens

Ejemplos de validacion local:

- `401 -> 218` tokens aproximados
- `312 -> 144` tokens aproximados
- `290 -> 227` tokens aproximados
- `337 -> 240` tokens aproximados

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
