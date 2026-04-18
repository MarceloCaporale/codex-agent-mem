# codex-agent-mem

Otros idiomas: [English](./README.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

Memoria portable y local-first para Codex y flujos con agentes de programacion.

codex-agent-mem persiste hallazgos durables de los turnos del agente en SQLite local, expone recuperacion compacta via MCP y mantiene la capa de memoria auditable y bajo control del runtime, en lugar de esconderla dentro de un unico runtime proveedor.

## Estado

`0.6.0` es la release pública base actual.

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
- guardarrail contra cierre falso cuando todavia quedan pendientes, blockers o gaps de DoD
- metricas persistidas de cierre y compresion por proyecto
- API de inspeccion con FastAPI
- UI local de inspeccion en `/ui`
- servidor MCP por stdio con:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
  - `mem_open_work`
  - `mem_completion_check`
  - `mem_context_pack`
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
