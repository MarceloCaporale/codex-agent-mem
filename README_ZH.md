# codex-agent-mem

其他语言版本：[English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [日本語](./README_JA.md)

面向 Codex 和编程代理工作流的可移植、本地优先记忆层。

codex-agent-mem 会把代理每个 turn 中的持久化结论保存到本地 SQLite，通过 MCP 提供紧凑检索，并让记忆层保持可审计、由运行时自己掌控，而不是被隐藏在某个单一厂商运行时内部。

## 状态

`0.2.0` 是当前的公开基础版本。

当前已实现：

- Codex 在 `agent-turn-complete` 上的 `notify` 写入
- 基于 FTS5 的本地 SQLite 持久化
- 对 `session_summary` 和 `decision` 的启发式提取
- FastAPI 检查 API
- 通过 stdio 运行的 MCP 服务器，包含：
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
- 自动化测试

当前有意不包含：

- embeddings
- 向量存储
- UI
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
pipx install "git+https://github.com/<org>/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### 方案 B：本地开发安装

```powershell
git clone <repo-url>
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

该命令会输出 `notify` 和 `[mcp_servers."codex-agent-mem"]` 配置块，可直接粘贴到 `~/.codex/config.toml`。

示例文件也位于 [examples/codex](./examples/codex/)。

## 本地运行

启动检查 API：

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
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
