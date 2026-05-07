# codex-agent-mem

<p align="center">
  <img src="docs/assets/codex-agent-mem-social-preview.png" alt="codex-agent-mem: persistent local memory for MCP clients" width="100%">
</p>

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/MarceloCaporale/codex-agent-mem)

Outros idiomas: [English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md) | [日本語](./README_JA.md)

**Memória MCP portátil, auditável e local-first para agentes de IA e fluxos de coding compatíveis com MCP.**

`codex-agent-mem` mantém memória durável de projeto fora do runtime do modelo, comprime continuidade em working packs menores e carrega estado operacional entre sessões para que agentes de IA compatíveis com MCP possam retomar com menos repetição, menos falsos "done" e mais controle sobre o que entra no contexto.

Tudo é armazenado e processado localmente por este MCP: banco SQLite, índice FTS, snapshots, metadata de telemetria e a UI opcional de inspeção. `codex-agent-mem` não envia sua memória, dados do projeto, prompts ou telemetria para nenhum servidor externo. Clientes MCP ainda podem expor resultados de ferramentas ao modelo ou serviço que você configurar, então trate a memória recuperada como saída local de ferramenta entregue a esse cliente.

Nascido para fluxos Codex e GPT, `codex-agent-mem` virou uma camada portátil de memória MCP para runtimes compatíveis com MCP, incluindo Codex CLI/Desktop, Claude Code, Google Gemini CLI, fluxos Qwen Code usando modelos Ollama e outros stacks locais ou de terceiros para agentes CLI. A validação é rastreada por cliente/runtime e nível de evidência. Detalhes específicos por modelo ficam nos docs de validação para que este README descreva a superfície pública sem exagerar nenhum runtime.

`codex-agent-mem` roda localmente, mantém a memória auditável e sob demanda, e não envia sua memória armazenada para nenhum serviço externo.

Baseline pública. Construída em slices pequenos e testáveis, ainda em evolução, mas já alinhada para uso real.

## Novidades na v1.0.x

- v1.0.1 corrige um caminho de `idle-timeout` entre o daemon local e a bridge stdio que podia aparecer como falso incidente `Transport closed` quando `--daemon-url` era usado.
- v1.0.1 serializa o tratamento compartilhado de requests dentro do daemon local threaded opcional para que uma única instância SQLite não seja usada de forma concorrente.
- v1.0.1 endurece a superfície pública local-first do daemon: bind apenas em loopback, bearer token opcional para `/mcp`, `/health` sanitizado e encaminhamento de token pela bridge stdio.
- v1.0.1 adiciona um guardrail de hierarquia de instruções no contexto gerado: memória recuperada é contexto auxiliar de projeto, não instrução de maior prioridade; é um guardrail básico, não proteção completa contra prompt injection.
- v1.0.1 documenta que a memória SQLite local é plaintext por padrão na linha pública 1.0.x e não deve ser tratada como cofre de segredos.
- v1.0.1 normaliza payloads MCP de tools que retornam listas para que `structuredContent` use raízes objeto como `{items, count}` em vez de arrays raiz, melhorando compatibilidade com clientes estritos como Claude Code.
- v1.0.1 adiciona recuperação por sessão persistida: `mem_session_list` lista sessões recentes, `mem_scope_resolve` prioriza lanes persistidos a partir de hints explícitos, `mem_bootstrap_context` evita packs project-wide de início quando há contêineres ambíguos, e `session_id` opcional filtra tools de recuperação para que escopos amplos não misturem chats ou agentes. Packs project-wide que cruzam várias sessões ou sub-scopes inferidos emitem um aviso visível e recomendam narrowing antes de tratar o pack como contexto ativo. Isso não é consciência live do turno atual.
- v1.0.1 mantém instalações normais de continuidade em modo writable; `--read-only` é um modo explícito de auditoria/debug/retrieval-only, não o modo operacional padrão.

- perfis MCP de baixo impacto: `minimal`, `standard` e `full`
- modo `--read-only` explícito de auditoria/debug que bloqueia tools mutantes e evita escritas laterais
- inicialização lazy do SQLite para conexões MCP não usadas
- respostas MCP compactas por padrão, mantendo o payload completo em `structuredContent`
- suporte a `known_pack_hash` / `not_modified` para não reenviar packs de continuidade sem mudanças
- diagnósticos runtime com heartbeat, spawn-storm warning, telemetria opcional e daemon/bridge stdio opcional

Releases recentes: [v1.0.1 Transport + Local Security Hotfix](./CHANGELOG.md#101---prepared-2026-05-06) | [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Snapshot (fixtures sintéticos v1.0)

| Cenário | Perfil | Tokens fonte | Tokens pack | Redução | `not_modified` | Tools | Lazy init | Read-only |
|---|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | `minimal` | 1,841 | 253 | 86.26% | true | 4 | false->true | true |
| Medium agent workflow | `minimal` | 4,855 | 270 | 94.44% | true | 4 | false->true | true |
| Large repeated audit | `minimal` | 9,731 | 269 | 97.24% | true | 4 | false->true | true |
| Sub-agent handoff example | `minimal` | 6,523 | 276 | 95.77% | true | 4 | false->true | true |

Nesses fixtures reproduzíveis, o contexto operacional repetido foi reduzido de ~22,950 tokens fonte para ~1,068 tokens de pack, uma redução aproximada de 95.35%. Isso não é uma garantia universal; mostra o efeito quando um agente normalmente reenviaria a mesma continuidade do projeto.

`Tools=4` corresponde ao perfil `minimal` anterior ao session-aware usado nesses fixtures. Na v1.0.1, `minimal` também inclui `mem_session_list`, `mem_scope_resolve` e `mem_bootstrap_context`, e o perfil `standard` expõe 20 tools para recuperação, governança e auditoria mais amplas.

### Snapshot de validação runtime

| Runtime | Configuração | Métricas observadas | Resultado |
|---|---|---|---|
| Default MCP writable | Bridges locais Codex/Gemini/Claude, `read_only=false`; `full` quando tools writable são necessárias | `mem_note_create` escreveu notas manuais indexadas e `mem_search` / `mem_context_pack` as recuperaram; `mem_snapshot_create(project_key, label, session_id)` registrou proveniência de alta confiança | Smokes writable de manual-note e snapshot-provenance passaram |
| Codex Desktop | Codex Desktop, MCP stdio, fixture retrieval-only v1.0 com `minimal`, `read-only`, `compact` | ~22,950 tokens fonte -> ~1,068 tokens de pack, ~95.35% menos contexto repetido, `not_modified=true` em packs repetidos | Validação MCP retrieval-only mais verificação pública reproduzível; continuidade writable é coberta pela linha anterior |
| Codex CLI / `codex exec` | Caminho MCP stdio do Codex CLI, execução curta / efêmera | mesmo servidor MCP local e estilo de configuração que Desktop; lifecycle curto de CLI validado separadamente do comportamento long-lived do host Desktop | Caminho Codex CLI validado |
| Google Gemini CLI | MCP stdio `codex-agent-mem`, validação retrieval-only explícita com `standard`, `read-only`; `compact` quando payload estruturado é visível, caso contrário `verbose` | processo estável, contador de requests subiu como esperado, payloads com raiz objeto verificados onde estavam visíveis | Validação MCP retrieval-only com caveat de exposição do cliente |
| Claude Code | Claude Opus 4.7, apenas MCP stdio `codex-agent-mem`, validação retrieval-only explícita com `standard`, `read-only`, `compact` | requests `3 -> 8`, lazy init `false -> true`, `same_db_process_count=2` com um host Claude Code ativo, `spawn_storm_warning=false`, `mem_search count=2` | Validação MCP retrieval-only passou |
| Qwen Code | Qwen Code 0.15.0, Ollama local, `qwen3.6:latest`, validação retrieval-only explícita com `standard`, `read-only`, `compact` | chamadas MCP reais a `mem_context_pack`, `mem_search`, `mem_open_work`, `mem_completion_check`, `mem_health_runtime`; requests `8`, lazy init `true`, `spawn_storm_warning=false`, `not_modified=true` | Validação MCP local retrieval-only passou |
| Smokes de modelos Qwen locais | Qwen Code 0.15.0 com modelos Ollama `qwen3.6:35b-a3b-q8_0` e `qwen3.5:9b` | ambos os modelos responderam smoke CLI e invocaram `mem_health_runtime` via MCP stdio; retrieval-only `read_only=true`, saídas limpas por `stdin_eof` | Smokes locais de modelos passaram |
| DeepSeek-V3.2 | Qwen Code 0.15.0, `deepseek-v3.2:cloud` via Ollama Cloud, validação retrieval-only explícita com `standard`, `read-only`, `compact` | chamadas MCP reais a `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `spawn_storm_warning=false`, `not_modified=true` | Validação MCP cloud-backed retrieval-only passou |
| Minimax M2.5 | Qwen Code 0.15.0, `minimax-m2.5:cloud` via Ollama Cloud, validação retrieval-only explícita com `standard`, `read-only`, `compact` | chamadas MCP reais a `mem_context_pack`, `mem_search`, `mem_health_runtime`; requests `6`, `not_modified=true` | Validação MCP cloud-backed retrieval-only passou |
| Kimi Code CLI | Kimi Code CLI 1.38.0, MCP stdio `codex-agent-mem`, validação retrieval-only explícita com `standard`, `read-only`, `compact` | `kimi mcp test codex-agent-mem` conectou e listou as tools esperadas do perfil standard; validação completa com tool-calls de Kimi K2.5 / Kimi K2.6 segue em avaliação contínua | Conexão MCP retrieval-only validada; não se afirma validação model-run |
| Grok / xAI | Nota de compatibilidade em nível de protocolo | Comportamento MCP stdio / JSON-RPC revisado em nível de protocolo | Nota de protocolo |

Grok / xAI aparece como nota de compatibilidade em nível de protocolo, não como validação live de tool-calls do modelo. As linhas validadas live são os pares MCP cliente/modelo medidos diretamente: Codex Desktop/CLI, Google Gemini CLI, Claude Code, Qwen Code, smokes de modelos Qwen locais, DeepSeek-V3.2 via Ollama Cloud, Minimax M2.5 via Ollama Cloud e validação de conexão Kimi Code CLI. Em geral, `codex-agent-mem` é agnóstico ao modelo na camada MCP; novos pares são adicionados quando suas medições live são capturadas.

## Resultados verificáveis

`codex-agent-mem` inclui um sandbox de verificação reproduzível e um export público de evidência para v1.0.0. A abordagem com fixtures é intencional: o MCP otimiza o manejo repetível de contexto operacional, então a evidência pública mantém esse contexto repetido controlado em vez de transformar cada execução em uma conversa diferente.

A evidência pública v1.0.x combina fixtures reproduzíveis de verificação com validação MCP live nos runtimes listados acima. Ela reporta compressão de contexto, prevenção de reenvio com `known_pack_hash`, inicialização lazy, superfície mínima de tools, segurança do modo read-only explícito, response diet, telemetria local, controle de fechamento e um exemplo com sub-agente.

Veja: [Verification Evidence](./docs/verification/) e [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md).

## Claude Code e claude-mem

`codex-agent-mem` roda no Claude Code como servidor MCP stdio padrão. Ele não instala hooks de início de sessão, stop hooks nem sumarização automática post-turno. A memória é recuperada sob demanda por tools MCP como `mem_context_pack`, `mem_search`, `mem_open_work` e `mem_completion_check`.

Se você já usa `claude-mem`, as duas ferramentas podem coexistir tecnicamente. Para fluxos de menor overhead e menor latência, use uma única camada de memória ativa por vez. Em validação local com um host Claude Code ativo, `codex-agent-mem` sozinho manteve o runtime compacto (`same_db_process_count=2`, `spawn_storm_warning=false`). Ao rodar junto com `claude-mem`, a superfície visível subiu para 61 tools, um bloco de memória de início de sessão de cerca de 6,995 tokens foi adicionado, e atrasos post-turno por stop hook apareceram. Isso não quebra `codex-agent-mem`, mas torna os resultados mais difíceis de comparar e pode aumentar overhead e latência.

Use `codex-agent-mem` quando preferir memória local-first, auditável, pull-based, com recuperação explícita e checks determinísticos de fechamento. Use plugins adicionais de memória apenas quando você quiser intencionalmente o comportamento automático baseado em hooks deles.

Para fluxos Claude Code sensíveis a tokens, `codex-agent-mem` é desenhado para baixo overhead por padrão: sem injeção no início da sessão, sem sumarização por stop hook, respostas compactas, budgets explícitos e atalho `pack_hash` / `not_modified` quando o pack não mudou.

## Complemento opcional: clean-process-ended

`codex-agent-mem` v1.0.1 e `clean-process-ended` ([GitHub](https://github.com/MarceloCaporale/clean-process-ended)) v0.7.2 funcionam de forma independente, mas resolvem problemas vizinhos em fluxos locais com agentes.

- `codex-agent-mem` preserva continuidade: memória de projeto, packs de contexto escopados, notas manuais, snapshots, trabalho aberto, blockers e checks determinísticos de fechamento.
- `clean-process-ended` cobre higiene de processos locais: diagnóstico ownership-first, checks de fechamento em dry-run e recibos compactos de janitor.

Juntos, eles melhoram o fechamento de tarefas: recuperar contexto, finalizar o trabalho, checar o estado local de processos e armazenar evidência compacta de fechamento sem tornar nenhum dos dois MCPs uma dependência obrigatória do outro.

## O que você recebe

### Continuidade

- **Continuidade compacta, não replay bruto**: transforma contexto repetido da sessão em packs menores para `AGENTS.md` quando a compressão realmente compensa
- **Estado operacional entre sessões e agentes**: mantém objetivo, constraints, trabalho pendente, blockers, Definition of Done e guardrails de escopo visíveis e reutilizáveis para que o contexto não fique preso a um modelo, uma sessão ou uma UI de provedor
- **Integração MCP-nativa**: roda como servidor MCP stdio local para Codex, Claude Code, Google Gemini CLI, Qwen Code e outros clientes compatíveis com MCP; `notify` do Codex e sync opcional de `AGENTS.md` continuam disponíveis quando úteis
- **Economia de tokens para fluxos com agentes**: melhora o uso de tokens em trabalho repetido com agentes ao reduzir replay de continuidade quando o pack compacto vence; os fixtures públicos v1.0 mostram reduções de 86% a 97% em cenários de contexto repetido

### Controle de fechamento

- **Controle determinístico de fechamento**: expõe `mem_open_work` e `mem_completion_check` para que trabalho aberto pese mais que claims antigos de conclusão
- **Retenção de escopo**: carrega must-not-drop continuity, mudanças recentes e blockers ativos em vez de apenas decisões

### Governança e auditoria

- **Seleção governada de memória**: aplica policies de projeto, regras de inheritance e eventos de repair em vez de misturar tudo cegamente
- **Memória MCP inspecionável**: a UI local `/ui` permite navegar mudanças recentes, scope guard, provenance, health, snapshots, estado de governança e memória armazenada sem abrir o SQLite manualmente
- **Totalmente local e auditável**: SQLite + FTS5, provenance, diagnósticos de health, snapshots e UI local de inspeção sem serviço externo de memória e sem sync outbound de memória
- **Fronteira local de segurança clara**: v1.0.1 endurece acesso loopback ao daemon, bearer-token opcional, `/health` sanitizado e hierarquia de instruções do contexto gerado; isso não é proof contra prompt injection, e o banco SQLite público 1.0.x continua plaintext por padrão e não deve ser usado como cofre de segredos

Docs principais: [AGENTS.md](./AGENTS.md) | [Quickstart](./docs/quickstart.md) | [Integração Codex](./docs/codex-integration.md) | [Nota Codex Desktop](./docs/codex-desktop-lifecycle-note.md) | [Support Matrix](./docs/support-matrix.md) | [Design Decisions](./docs/design-decisions.md)

Criado para auditorias longas, continuidade de projetos em múltiplos passos e fluxos onde a falha real não é apenas esquecer decisões, mas também perder escopo, deixar blockers invisíveis e declarar conclusão cedo demais.

## Status

`1.0.1` é a release atual de manutenção 1.0.x. `1.0.0` continua sendo a baseline pública de verificação para as métricas reproduzíveis abaixo.

Funciona hoje:

- ingestão `notify` do Codex em `agent-turn-complete`
- persistência local SQLite com FTS5
- extração heurística de `session_summary`, `decision`, `objective`, `constraint`, `pending_item`, `completed_item`, `blocker` e `completion_claim`
- Definition of Done hierárquica em `project_dod`, `mission_dod` e `session_dod`
- packs gerados de working memory com budget aproximado de tokens e stats de compressão
- packs com budget `micro`, `normal` e `full`
- sync opt-in de `AGENTS.md` com `--sync-project-doc` quando o pack gerado é menor que o contexto fonte
- carry-forward de estado operacional para que a próxima execução recupere objetivo, trabalho pendente, blockers e guardrails de escopo
- controle determinístico de fechamento com `mem_open_work` e `mem_completion_check`
- deltas de mudanças recentes por `mem_recent_changes`
- continuidade de escopo e guardrails must-not-drop por `mem_scope_guard`
- guardrails contra falso fechamento que impedem "done" de sobrepor trabalho aberto quando ainda há pendências, blockers ou gaps de DoD
- métricas de sync de contexto e fechamento persistidas por projeto
- seleção automática de budget para context packs quando `budget=auto`
- provenance de memória persistida por observação e consultável por `mem_provenance`
- diagnóstico de health por `mem_health`
- diagnóstico runtime MCP por `mem_health_runtime`
- notas operacionais manuais com `mem_note_create`, indexadas para `mem_search` e elegíveis para `mem_context_pack`
- snapshots versionados de projeto com `mem_snapshot_create`, `mem_snapshot_list` e `mem_snapshot_restore`
- políticas de memória governada por `mem_policy_validate`, `mem_policy_add`, `mem_policy_list` e `mem_policy_remove`
- links seletivos de inheritance por `mem_inheritance_add`, `mem_inheritance_list` e `mem_inheritance_remove`
- propostas de repair governado e eventos derivados por `mem_repair_propose` e `mem_repair_apply`
- perfis MCP de baixo impacto por `--profile minimal|standard|full`
- modo explícito read-only de auditoria/debug por `--read-only`
- texto MCP compacto com `structuredContent` completo
- reutilização de pack de continuidade com `known_pack_hash` / `not_modified`
- cache in-process curto para tools de leitura custosas
- inicialização lazy do SQLite para conexões MCP baratas quando não usadas
- health runtime enriquecido com perfil, mutabilidade, cache, lazy-init, heartbeat e diagnósticos spawn-storm
- telemetria runtime local opcional por `--telemetry-mode off|summary|debug`
- daemon local opcional por `codex-agent-mem-daemon` e modo bridge stdio com `--daemon-url`
- API de inspeção FastAPI
- UI local de inspeção em `/ui`, incluindo mudanças recentes, scope guard, provenance, health, snapshots e estado de governança
- CLI local de policy com `codex-agent-mem-policy`
- servidor MCP stdio com:
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
- testes automatizados

Fora de escopo de propósito por enquanto:

- embeddings
- vector stores
- ingestão Codex App Server
- adaptador de hooks Codex
- adaptador Ollama
- orquestração multiagente

## Por que este repositório existe

- Fluxos com agentes frequentemente precisam de contexto durável fora de um único processo runtime.
- Retrieval sozinho não resolve a falha maior: perder escopo e forçar o usuário a repetir contexto anterior.
- Um bloco compacto de continuidade ou context pack MCP pode reduzir quanto contexto anterior precisa ser repetido manualmente.
- Carregar apenas decisões não basta; o runtime também precisa de objetivo ativo, trabalho aberto, blockers e uma regra contra falso fechamento.
- SQLite mantém a implementação local-first, auditável e fácil de inspecionar.
- A release atual foca de propósito em um slice estreito e testável, não em uma plataforma ampla inacabada.
- Hosts MCP long-lived e short-lived podem se comportar diferente sob carga; veja os docs de validação para a fronteira runtime exata.

## Modelo de instalação

`codex-agent-mem` é instalado como pacote Python local e exposto a clientes compatíveis com MCP por comandos stdio.

O padrão estável é:

1. instalar o pacote
2. apontar o cliente MCP para o comando instalado
3. manter o banco de memória local e auditável

Snippets específicos do Codex para `notify` e `mcp_servers` são gerados por `codex-agent-mem-bootstrap-codex`; outros clientes MCP usam seus próprios arquivos de configuração.

## Quickstart

Se você quer o caminho mais curto do clone até um setup local funcionando:

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

Para Codex, cole o snippet gerado em `~/.codex/config.toml`. Para outros clientes MCP, use o comando stdio comum em [Configurar clientes MCP](#configurar-clientes-mcp).

## Instalação

### Opção A: `pipx` a partir do GitHub

Instale diretamente pela URL do repositório:

```bash
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

### Opção B: instalação local de desenvolvimento

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

O ponto de entrada do servidor MCP é o mesmo para qualquer cliente compatível:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Aponte seu cliente compatível com MCP para esse comando stdio instalado. Os caminhos públicos validados em v1.0.x incluem Codex CLI/Desktop, Claude Code, Google Gemini CLI, Qwen Code com modelos Qwen locais via Ollama, DeepSeek-V3.2 e Minimax M2.5 via Ollama Cloud, além de validação de conexão Kimi Code CLI.

### Helper Codex

Gere um snippet pronto para colar:

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Para Codex, isso imprime o bloco `notify`, o bloco `[mcp_servers."codex-agent-mem"]`, um idle-timeout stdio explícito e aprovações de tools MCP que você pode colar em `~/.codex/config.toml`.

Para sessões long-lived do Codex Desktop, prefira um MCP idle timeout maior, como `--idle-timeout-seconds 1800`, para que o thread Desktop tenha menos chance de manter um transporte stdio fechado. Para execuções CLI curtas ou `codex exec`, `300` segundos normalmente basta e limpa mais rápido.

A reinjeção automática em `AGENTS.md` agora é opt-in. Adicione `--sync-project-doc` ao comando `notify` apenas se você quiser que blocos gerados de working-memory sejam escritos de volta no working directory.

## Como agentes devem usar

Depois de configurado, o agente deve usar `codex-agent-mem` proativamente quando continuidade importa. Você não deveria precisar repetir "use o MCP de memória" a cada poucos turnos.

Padrão recomendado:

- comece com `mem_bootstrap_context` quando decisões anteriores, trabalho pendente, blockers, constraints ou estado do projeto puderem importar; passe título de chat, thread, cwd ou repo quando o host expuser isso
- chame `mem_context_pack` diretamente apenas quando o escopo já for explícito, idealmente com `session_id` em workspaces amplos
- passe `known_pack_hash` em checagens repetidas para que packs sem mudança retornem `not_modified` em vez de reenviar contexto
- use `mem_search` apenas quando o pack compacto não for suficiente
- antes de afirmar conclusão, chame `mem_open_work` e `mem_completion_check` para tarefas de implementação, validação, publicação, migração ou documentação

É daí que vem a economia prática de tokens: continuidade compacta primeiro, expansão direcionada apenas quando necessário e nenhum reenvio de pack quando nada mudou.

Arquivos de exemplo ficam em [examples/codex](./examples/codex/), com notas de fluxos via Ollama em [examples/ollama](./examples/ollama/).

## Rodar localmente

Inicie a API de inspeção:

```bash
codex-agent-mem-api --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Então abra:

```text
http://127.0.0.1:37770/ui
```

Inicie o servidor MCP:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

O transporte MCP atual é stdio. Isso significa que um processo por conexão de host é normal; não é um daemon singleton. O idle timeout defensivo existe para permitir que instâncias não usadas ou órfãs saiam de forma limpa.

Defaults recomendados: use um timeout maior para sessões Codex Desktop, por exemplo `1800` segundos, e um timeout menor para execuções CLI/efêmeras, por exemplo `300` segundos.

Reconstrua manualmente o bloco de continuidade gerado para um diretório:

```bash
codex-agent-mem-refresh-context --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db" --project-key YOUR_PROJECT --cwd /path/to/project
```

```powershell
codex-agent-mem-refresh-context --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --project-key YOUR_PROJECT --cwd C:\Path\To\Project
```

## Verificação rápida

Rode o smoke test:

```bash
codex-agent-mem-smoke --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Isso insere um turno de exemplo, extrai observações e verifica recuperação recente e geração de project brief.

## Eficiência de tokens: o que economiza tokens hoje

- O pacote compila um working-memory pack menor a partir de turns recentes, decisões duráveis e estado operacional derivado.
- Quando `--sync-project-doc` está habilitado e esse pack é realmente menor que o contexto fonte, ele é sincronizado em `AGENTS.md` para o working directory.
- Retrieval MCP e sync opcional de `AGENTS.md` permitem que sessões futuras comecem com continuidade comprimida em vez de forçar você a repetir o escopo antigo.
- `mem_context_pack` expõe o mesmo pack compacto por MCP para recuperação sob demanda.
- O pack agora carrega trabalho pendente e blockers, para que uma execução futura recupere "o que falta" em vez de apenas "o que foi decidido".

Isso é eficiência de tokens para fluxos com agentes, não compressão mágica. `codex-agent-mem` melhora a economia de contexto ao reduzir contexto repetido do projeto, reutilizar packs sem mudança via `known_pack_hash` e permitir que agentes expandam apenas a memória de que precisam.

## Redução aproximada de tokens

Em linguagem simples: isso normalmente busca reduzir a quantidade de contexto repetido que você precisa reenviar, não eliminá-la completamente.

O que podemos dizer honestamente a partir da validação local:

- os fixtures públicos v1.0 reduziram contexto repetido de ~22,950 tokens fonte para ~1,068 tokens de pack, cerca de `95.35%` naquele cenário controlado
- os cenários individuais da suíte de fixtures ficaram entre `86%` e `97%` de redução
- checks runtime live confirmaram retrieval MCP compacto, lifecycle de processo estável, comportamento object-root/no-reinjection onde visível e snapshot provenance writable para bridges locais Codex/Gemini/Claude

Exemplos do sandbox público v1.0:

- `1,841 -> 253` tokens aproximados
- `4,855 -> 270` tokens aproximados
- `9,731 -> 269` tokens aproximados
- `6,523 -> 276` tokens aproximados

Importante: isso não é garantia fixa por prompt. Se o pack compacto não for realmente menor que o contexto fonte, `codex-agent-mem` pula a reinjeção em vez de fingir que economizou tokens.

## O que isso ajuda a detectar hoje

- perda do objetivo original depois de algumas execuções
- redução silenciosa de escopo quando o usuário pediu mais
- declaração de conclusão enquanto ainda existe trabalho pendente
- blockers esquecidos que fariam a próxima execução retomar como se a tarefa estivesse terminada

## Estrutura do repositório

- [src/codex_agent_mem](./src/codex_agent_mem/) - código do pacote
- [tests](./tests/) - testes executáveis
- [examples/codex](./examples/codex/) - exemplos de integração com Codex
- [examples/ollama](./examples/ollama/) - notas para fluxos via Ollama
- [scripts](./scripts/) - helpers locais de bootstrap
- [docs](./docs/) - arquitetura, integração, quickstart e release notes

## Mapa de documentação

- [AGENTS.md](./AGENTS.md) - mapa do repo e guia operacional para agentes de IA compatíveis com MCP
- [docs/quickstart.md](./docs/quickstart.md) - caminho mais curto de instalação e primeiro uso
- [docs/codex-integration.md](./docs/codex-integration.md) - como notify e MCP se encaixam no Codex
- [docs/verification](./docs/verification/) - métricas públicas reproduzíveis e evidência v1.0.0
- [docs/support-matrix.md](./docs/support-matrix.md) - suporte atual e gaps conhecidos
- [docs/codex-desktop-lifecycle-note.md](./docs/codex-desktop-lifecycle-note.md) - comportamento observado do Codex Desktop e mitigações práticas
- [docs/design-decisions.md](./docs/design-decisions.md) - decisões explícitas de produto e arquitetura
- [docs/architecture.md](./docs/architecture.md) - arquitetura técnica portátil da release atual
- [docs/validation](./docs/validation/) - níveis de validação, suporte runtime, comportamento de clientes e notas públicas de evidência
- [CONTRIBUTING.md](./CONTRIBUTING.md) - fluxo de contribuição e barra de qualidade
- [SECURITY.md](./SECURITY.md) - escopo de suporte e guia de reporte de segurança
- [docs/discoverability.md](./docs/discoverability.md) - descrição GitHub, topics e framing de release recomendados

## Superfície de release

Este repositório inclui:

- layout limpo de pacote na raiz
- `pyproject.toml` instalável
- entry points de comandos
- testes
- workflow de CI
- licença
- changelog

## Autor

Criado e mantido por Marcelo Caporale.

- X: [@MarceloCaporale](https://x.com/MarceloCaporale)
- Studio: [Visual AI Media](https://visualaimedia.com)
- Lab: [Visual Systems Lab](https://visualsystemslab.com)
