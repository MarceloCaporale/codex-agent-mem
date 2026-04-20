# codex-agent-mem

其他语言版本：[English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [日本語](./README_JA.md)

面向 Codex 和编程代理工作流的可移植、可审计、本地优先连续性记忆层。

codex-agent-mem 将持久化项目记忆放在模型运行时之外，把连续性压缩成更小的工作 pack，并跨会话保留操作状态，让 Codex 以更少重复、更少误判完成、更多上下文控制继续工作。

公开基线版本。以小而可验证的切片构建，仍在继续演进，但已经面向真实使用。

## v0.9.0 新增内容

- 通过治理策略实现显式的记忆包含与排除
- 在项目之间进行选择性 inheritance，而不是盲目混合连续性
- 基于 health 的 repair 提案与衍生 repair 事件
- 在本地 UI 与文档中可见的 governance 信息

可见版本: [v0.9.0 Governance](./CHANGELOG.md#090---2026-04-18) | [v0.8.0 Persistence & Observability](./CHANGELOG.md#080---2026-04-18)

## 你得到的能力

### 连续性

- **压缩连续性，而不是反复重放原始上下文**：只有当生成 pack 确实更小时才同步到 `AGENTS.md`
- **跨会话保留操作状态**：持续保存 objective、constraints、pending work、blockers、Definition of Done 与 scope guardrails
- **原生适配 Codex**：围绕 `notify`、MCP stdio、可选的 `AGENTS.md` 同步以及更稳健的运行时清理设计
- **实际可见的 token 节省**：当紧凑 pack 胜出时，重复上下文通常可减少约 `20%` 到 `55%`

### 闭合控制

- **确定性的闭合控制**：`mem_open_work` 与 `mem_completion_check` 让未完成工作优先于陈旧的完成声明
- **范围保持**：不仅保留决策，也延续 recent changes、must-not-drop、blockers 与活动连续性

### 治理与审计

- **受治理的记忆选择**：通过 policies、inheritance 与 repairs 控制进入 pack 的内容，而不是盲目混入
- **完全本地且可审计**：SQLite + FTS5、provenance、health、snapshots 和本地 UI，无需外部记忆服务

适合长时间审计、复杂项目连续工作，以及那些不仅要记住决策，还要避免丢失范围和过早宣告完成的场景。

## 状态

`0.9.0` 是当前的基础版本。

当前已实现：

- Codex 在 `agent-turn-complete` 上的 `notify` 写入
- 基于 FTS5 的本地 SQLite 持久化
- 对 `session_summary`、`decision`、`objective`、`constraint`、`pending_item`、`completed_item`、`blocker` 和 `completion_claim` 的启发式提取
- 分层的 Definition of Done：`project_dod`、`mission_dod`、`session_dod`
- 生成带有近似 token 预算的紧凑连续性 pack
- `micro`、`normal`、`full` 三档 pack 预算
- 当 pack 确实小于源上下文时可选地同步到 `AGENTS.md`
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

- 在较理想的场景下，紧凑 pack 对重复上下文的压缩大约在 `20%` 到 `55%`
- 很多真实运行的结果，大约落在 `减少三分之一到一半` 的重复上下文
- 如果某个流程原本需要重新发送大约 `1000` token 的旧上下文，一个合理的预期通常会更接近 `450` 到 `800` token

本地验证示例：

- `401 -> 218` 近似 token
- `312 -> 144` 近似 token
- `290 -> 227` 近似 token
- `337 -> 240` 近似 token

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
