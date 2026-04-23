# codex-agent-mem

其他语言版本：[English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [日本語](./README_JA.md)

面向 Codex、Claude、本地编程代理和第三方 CLI workflows 的可移植、可审计、本地优先连续性记忆层。

codex-agent-mem 将持久化项目记忆放在模型运行时之外，把连续性压缩成更小的工作 pack，并跨会话保留操作状态，让 Codex 以更少重复、更少误判完成、更多上下文控制继续工作。

所有内容都由这个 MCP 在本地保存和处理：SQLite 数据库、FTS 索引、snapshots、telemetry metadata，以及可选的本地 inspector UI。`codex-agent-mem` 不会把你的 memory、project data、prompts 或 telemetry 发送到任何外部服务器。

`codex-agent-mem` 最初为 Codex 和 GPT-5.x workflow 而生，但现在已经扩展为适用于 MCP-compatible agent runtimes 的 portable MCP memory layer，例如 Codex CLI、Codex Desktop、使用 Gemini 3.1 Pro 的 Gemini CLI、使用 Opus 4.7 或 Sonnet 4.6 的 Claude Code、通过 Ollama 使用本地 Qwen 3.6 / Qwen 3.5 models 的 Qwen Code、通过 Ollama Cloud 使用 DeepSeek-V3.2 与 Minimax M2.5，以及自定义本地 agent stacks。持续评估中：Kimi Code CLI、GLM-5、Kimi K2.5 与 Kimi K2.6。Kimi Code CLI 可以通过 stdio 连接到 `codex-agent-mem` MCP server；Kimi K2.5 / Kimi K2.6 的完整 live model tool-call validation 会单独测量后再声明。它也经过了针对 Grok / xAI 与 DeepSeek 类 MCP orchestrators 的 protocol-level compatibility 外部审计。

`codex-agent-mem` 在本地运行，保持 memory 可审计、pull-based，并且不会把已存储 memory 发送到任何外部服务。

Scope distinction: Codex CLI 和 Codex Desktop 的验证不等同于 ChatGPT web/app connector 验证，Claude Code 的验证也不等同于 Claude web / claude.ai 验证。ChatGPT web/app 与 Claude web 会作为未来独立 integration surfaces 跟踪，不作为 v1.0 validated runtimes 声明。

公开基线版本。以小而可验证的切片构建，仍在继续演进，但已经面向真实使用。

## v1.0.0 新增内容

- 低影响 MCP 运行模式：`minimal`、`standard`、`full`
- 真正的 `--read-only`，阻止可变更 tool 和旁路写入
- SQLite lazy initialization，让未使用的 MCP 连接保持轻量
- 默认返回紧凑 MCP 文本，完整 payload 保留在 `structuredContent`
- `known_pack_hash` / `not_modified`，避免重复发送未变化的连续性 pack
- heartbeat、spawn-storm warning、可选 telemetry，以及可选 daemon/stdio bridge

可见版本: [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Snapshot（v1.0 合成 fixtures）

| 场景 | Profile | Source tokens | Pack tokens | 节省 | `not_modified` | Tools | Lazy init | Read-only |
|---|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | `minimal` | 1,841 | 216 | 88.27% | true | 4 | false->true | true |
| Medium agent workflow | `minimal` | 4,855 | 233 | 95.20% | true | 4 | false->true | true |
| Large repeated audit | `minimal` | 9,731 | 232 | 97.62% | true | 4 | false->true | true |
| Sub-agent handoff example | `minimal` | 6,523 | 239 | 96.34% | true | 4 | false->true | true |

在这些可复现 fixtures 中，重复的 operational context 从约 22,950 source tokens 压缩到约 920 memory-pack tokens，约减少 96.0%。这不是通用保证；它展示的是当 agent 原本需要反复发送同一项目连续性时的效果。

`Tools=4` 指这些 fixtures 使用的 `minimal` profile。`standard` profile 会暴露 17 个 tools，用于更完整的 retrieval、governance 与 audit workflow。

### Runtime validation snapshot

| Runtime | 配置 | 观测指标 | 结果 |
|---|---|---|---|
| Codex Desktop | 在这个 Codex environment 中使用 GPT-5.4 的 Codex Desktop，reasoning effort xhigh，v1.0 合成 fixtures | 约 22,950 source tokens -> 约 920 pack tokens，重复上下文约减少 96.0%，重复 pack 返回 `not_modified=true` | 公开可复现验证 |
| Codex CLI / `codex exec` | Codex CLI MCP stdio path，short-lived / ephemeral execution | 使用与 Desktop 相同的 local MCP server 和 config style；short-lived CLI lifecycle 已与 long-lived Desktop host behavior 分开验证 | Validated Codex CLI path |
| Gemini CLI | Gemini 3.1 Pro，`codex-agent-mem` MCP stdio，`standard`，`read-only`，`compact` | 进程稳定，request 计数按预期增加，`mem_search` 返回对象根 `{items, count}` 且 `count=2` | live MCP 验证通过 |
| Claude Code | Claude Opus 4.7，仅启用 `codex-agent-mem` MCP stdio，`standard`，`read-only`，`compact` | requests `3 -> 8`，lazy init `false -> true`，单个 Claude Code host 活跃时 `same_db_process_count=2`，`spawn_storm_warning=false`，`mem_search count=2` | live MCP 验证通过 |
| Qwen Code | Qwen Code 0.15.0，本地 Ollama，`qwen3.6:latest`，`standard`，`read-only`，`compact` | 对 `mem_context_pack`、`mem_search`、`mem_open_work`、`mem_completion_check`、`mem_health_runtime` 发起真实 MCP 调用；requests `8`，lazy init `true`，`spawn_storm_warning=false`，`not_modified=true` | 本地 live MCP 验证通过 |
| Qwen 本地模型 smoke | Qwen Code 0.15.0 与 Ollama models `qwen3.6:35b-a3b-q8_0`、`qwen3.5:9b` | 两个模型都通过 CLI smoke，并通过 MCP stdio 调用 `mem_health_runtime`；requests `4`，`read_only=true`，干净 `stdin_eof` 退出 | 本地 live model smoke 通过 |
| DeepSeek-V3.2 | Qwen Code 0.15.0，通过 Ollama Cloud 使用 `deepseek-v3.2:cloud`，`standard`，`read-only`，`compact` | 对 `mem_context_pack`、`mem_search`、`mem_health_runtime` 发起真实 MCP 调用；requests `6`，`spawn_storm_warning=false`，`not_modified=true` | cloud-backed live MCP 验证通过 |
| Minimax M2.5 | Qwen Code 0.15.0，通过 Ollama Cloud 使用 `minimax-m2.5:cloud`，`standard`，`read-only`，`compact` | 对 `mem_context_pack`、`mem_search`、`mem_health_runtime` 发起真实 MCP 调用；requests `6`，`not_modified=true` | cloud-backed live MCP 验证通过 |
| Kimi Code CLI | Kimi Code CLI 1.38.0，`codex-agent-mem` MCP stdio，`standard`，`read-only`，`compact` | `kimi mcp test codex-agent-mem` 成功连接并列出 17 个 tools；Kimi K2.5 / Kimi K2.6 的 model tool-call validation 仍处于 continuous evaluation | MCP 连接已验证；不声明模型运行验证 |
| Grok / xAI | 外部 model/runtime audit；本机没有可用的 Grok CLI | 可通过 MCP stdio-capable orchestrator 或轻量 JSON-RPC stdio wrapper 实现 protocol compatibility | 已外部审计；非本机 live 验证 |

Grok 行是外部审计结果，不是这台机器上的本地 live CLI session。Qwen Code 现在已经通过 Ollama-backed models 和 MCP stdio 做过本地验证。DeepSeek-V3.2 与 Minimax M2.5 已通过 Ollama Cloud-backed models 做过 live validation，但这不是本地推理。Kimi Code CLI 已完成 MCP 连接验证，但 Kimi K2.5 / Kimi K2.6 的 model-level validation 仍作为 continuous evaluation 处理，因为完整模型需要单独的 runtime path。一般来说，`codex-agent-mem` 在 MCP 层是 model-agnostic。表格列出已经完成 live measurement 的 model/runtime pairs，新的 pair 会在捕获到测量结果后加入。对于没有 native MCP client 的 host，预期集成路径是轻量 JSON-RPC stdio wrapper 或 MCP-capable orchestrator。

## 可验证结果

`codex-agent-mem` 包含一个可复现的 verification sandbox，以及 v1.0.0 的公开 evidence export。

当前公开运行使用 **在这个 Codex environment 中使用 GPT-5.4 的 Codex Desktop、reasoning effort xhigh**，基于合成 fixtures 执行。它测量上下文压缩、通过 `known_pack_hash` 避免重复发送、lazy initialization、最小 tool surface、read-only safety、response diet、本地 telemetry、closure control，以及一个 sub-agent handoff 示例。这是 Codex Desktop validation，不是 ChatGPT web/app connector validation。

参见：[Verification Evidence](./docs/verification/) 和 [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md)。

## Claude Code 与 claude-mem

`codex-agent-mem` 在 Claude Code 中作为标准 MCP stdio server 运行。它不会安装 session-start hook、stop hook，也不会做自动 post-turn 总结。内存只在需要时通过 `mem_context_pack`、`mem_search`、`mem_open_work` 和 `mem_completion_check` 等 MCP tools 拉取。

如果你已经使用 `claude-mem`，两者技术上可以共存。对于低开销、低延迟 workflow，建议一次只启用一个 active memory layer。本地验证中，在单个 Claude Code host 活跃时，单独使用 `codex-agent-mem` 的 runtime 保持紧凑（`same_db_process_count=2`，`spawn_storm_warning=false`）。与 `claude-mem` 同时运行时，可见 tool surface 增加到 61 tools，session-start memory block 约 6,995 tokens，并观察到 post-turn stop-hook 延迟。这不会破坏 `codex-agent-mem`，但会让结果更难比较，并可能增加开销和延迟。

如果你想要 local-first、可审计、pull-based、显式 retrieval 和确定性的 closure checks，优先使用 `codex-agent-mem`。只有当你明确需要额外 memory plugin 的 hook-based 自动行为时，再启用它们。

对于 token-sensitive 的 Claude Code workflow，`codex-agent-mem` 默认设计为低开销：没有 session-start injection，没有 stop-hook summarization，使用 compact responses、显式 budgets，并通过 `pack_hash` / `not_modified` 对未变化的 pack 进行 short-circuit。

## 你得到的能力

### 连续性

- **压缩连续性，而不是反复重放原始上下文**：只有当生成 pack 确实更小时才同步到 `AGENTS.md`
- **跨会话保留操作状态**：持续保存 objective、constraints、pending work、blockers、Definition of Done 与 scope guardrails
- **原生适配 Codex**：围绕 `notify`、MCP stdio、可选的 `AGENTS.md` 同步以及更稳健的运行时清理设计
- **实际可见的 token 节省**：当紧凑 pack 胜出时减少重复连续性重发；公开 v1.0 fixtures 在 repeated-context 场景中显示 88% 到 97% 的减少

### 闭合控制

- **确定性的闭合控制**：`mem_open_work` 与 `mem_completion_check` 让未完成工作优先于陈旧的完成声明
- **范围保持**：不仅保留决策，也延续 recent changes、must-not-drop、blockers 与活动连续性

### 治理与审计

- **受治理的记忆选择**：通过 policies、inheritance 与 repairs 控制进入 pack 的内容，而不是盲目混入
- **完全本地且可审计**：SQLite + FTS5、provenance、health、snapshots 和本地 UI，无需外部记忆服务，也没有向外同步 memory

适合长时间审计、复杂项目连续工作，以及那些不仅要记住决策，还要避免丢失范围和过早宣告完成的场景。

## 状态

`1.0.0` 是当前的基础版本。

当前已实现：

- Codex 在 `agent-turn-complete` 上的 `notify` 写入
- 基于 FTS5 的本地 SQLite 持久化
- 对 `session_summary`、`decision`、`objective`、`constraint`、`pending_item`、`completed_item`、`blocker` 和 `completion_claim` 的启发式提取
- 分层的 Definition of Done：`project_dod`、`mission_dod`、`session_dod`
- 生成带有近似 token 预算的紧凑连续性 pack
- `micro`、`normal`、`full` 三档 pack 预算
- 通过 `--sync-project-doc`，在 pack 确实小于源上下文时可选地同步到 `AGENTS.md`
- 延续操作状态，让下一次会话能恢复目标、待办、阻塞项和范围保护规则
- 通过 `mem_open_work` 和 `mem_completion_check` 提供确定性的闭合检查
- 通过 `mem_recent_changes` 查看最近变化增量
- 通过 `mem_scope_guard` 提供范围连续性和不可丢失项守护
- 在仍有待办、阻塞项或 DoD 缺口时，提供防止“误判已完成”的 guardrail
- 每个项目都会持久化闭合检查和压缩指标
- 当使用 `budget=auto` 时自动选择最合适的上下文预算
- 为每条 observation 持久化 provenance，并可通过 `mem_provenance` 查询
- 通过 `mem_health` 提供项目健康诊断
- 通过 `mem_health_runtime` 提供 MCP 进程运行时诊断
- 通过 `mem_snapshot_create`、`mem_snapshot_list`、`mem_snapshot_restore` 提供版本化项目快照
- 通过 `mem_policy_validate`、`mem_policy_add`、`mem_policy_list`、`mem_policy_remove` 提供受治理的记忆策略
- 通过 `mem_inheritance_add`、`mem_inheritance_list`、`mem_inheritance_remove` 提供选择性继承链接
- 通过 `mem_repair_propose` 与 `mem_repair_apply` 提供受治理的修复建议和修复事件
- FastAPI 检查 API
- 位于 `/ui` 的本地检查界面，包含 recent changes、scope guard、provenance、health、snapshots 与 governance 状态
- 本地 policy CLI：`codex-agent-mem-policy`
- 通过 stdio 运行的 MCP 服务器，包含：
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
- 自动化测试

当前有意不包含：

- embeddings
- 向量存储
- Codex App Server 写入
- Codex hooks 适配器
- Ollama 适配器
- 多代理编排

## 重要说明

Codex 目前还不能通过一个 GitHub URL 一步安装任意 MCP 工具。

目前支持的路径仍然是：

1. 安装 Python 包
2. 在 Codex 中把 `notify` 和 `mcp_servers` 指向已安装的命令

这个仓库已经按这种流程整理好，便于稳定、可重复地使用。

## 安装

### 方案 A：通过 GitHub 使用 `pipx`

直接从仓库地址安装：

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### 方案 B：本地开发安装

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

## 配置 Codex

生成可直接粘贴的配置片段：

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

该命令会输出 `notify`、`[mcp_servers."codex-agent-mem"]`、显式的 stdio idle timeout，以及只读 MCP 工具的审批配置，可直接粘贴到 `~/.codex/config.toml`。

如果你还想启用自动 `AGENTS.md` 回写，请把 `--sync-project-doc` 加到 `notify` 命令里。

## Agent 应该如何使用

配置完成后，当连续性很重要时，agent 应主动使用 `codex-agent-mem`。你不应该每隔几轮就重复提醒它“使用 memory MCP”。

推荐模式：

- 当历史决策、未完成工作、blocker、约束或项目状态可能相关时，先调用 `mem_context_pack`
- 重复检查时传入 `known_pack_hash`，未变化的 pack 会返回 `not_modified`，而不是再次发送上下文
- 只有当紧凑 pack 不够时才使用 `mem_search`
- 在实现、验证、发布、迁移或文档任务中声明完成之前，调用 `mem_open_work` 和 `mem_completion_check`

实际 token 节省来自这个模式：先使用紧凑连续性，只在需要时展开细节，如果 pack 没变就不重复发送。

示例文件也位于 [examples/codex](./examples/codex/)。

## 本地运行

启动检查 API：

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

然后在浏览器打开：

```text
http://127.0.0.1:37770/ui
```

启动 MCP 服务器：

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

## 快速验证

运行 smoke 测试：

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

它会插入一个示例 turn，提取观察结果，并验证最近检索结果以及 `project_brief` 的生成。

## 大致的 token 节省

用最容易理解的话说：它的作用是减少你必须再次塞给 Codex 的重复上下文，而不是把这部分上下文完全消灭。

根据本地验证，目前可以诚实地这样描述：

- 公开 v1.0 fixtures 将重复上下文从约 22,950 source tokens 减少到约 920 pack tokens，在这个受控场景中约为 `96.0%`
- fixture suite 中的各个 repeated-context 场景减少幅度在 `88%` 到 `97%`
- Gemini CLI、Claude Code、Qwen Code 与通过 Ollama Cloud 的 DeepSeek-V3.2、Minimax M2.5 的 live runtime checks 确认了 compact MCP retrieval、稳定进程生命周期、read-only mode，以及在可见范围内的对象根/no-reinjection 行为

公开 v1.0 verification sandbox 示例：

- `1,841 -> 216` 近似 token
- `4,855 -> 233` 近似 token
- `9,731 -> 232` 近似 token
- `6,523 -> 239` 近似 token

重要说明：这不是对每个 prompt 的固定保证。如果生成的 pack 实际上并不比源上下文更小，`codex-agent-mem` 会跳过 reinjection，而不会假装自己节省了并不存在的 token。

## 仓库结构

- [src/codex_agent_mem](./src/codex_agent_mem/) - 包代码
- [tests](./tests/) - 可执行测试
- [examples/codex](./examples/codex/) - Codex 集成示例
- [scripts](./scripts/) - 本地 bootstrap 辅助脚本
- [docs](./docs/) - 架构与发布说明

## 发布面

此仓库包含：

- 清晰的根目录结构
- 可安装的 `pyproject.toml`
- 命令入口
- 测试
- CI 工作流
- 许可证
- 变更日志
