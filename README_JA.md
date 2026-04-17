# codex-agent-mem

他言語版: [English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md)

Codex とコーディングエージェントのワークフロー向けの、ポータブルでローカルファーストなメモリレイヤー。

codex-agent-mem は、エージェントの各ターンから得られた永続的な知見をローカル SQLite に保存し、MCP 経由でコンパクトな取得機能を提供します。また、メモリレイヤーを単一ベンダーのランタイム内部に隠すのではなく、監査可能でランタイム自身が管理できる状態に保ちます。

## 状態

`0.2.0` は現在の公開ベースリリースです。

現在動作しているもの:

- `agent-turn-complete` に対する Codex `notify` 取り込み
- FTS5 を使ったローカル SQLite 永続化
- `session_summary` と `decision` のヒューリスティック抽出
- FastAPI ベースの検査 API
- 以下を提供する MCP stdio サーバー:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
- 自動テスト

意図的にまだ対象外としているもの:

- embeddings
- ベクターストア
- UI
- Codex App Server 取り込み
- Codex hooks アダプター
- Ollama アダプター
- マルチエージェント・オーケストレーション

## 重要な前提

Codex は現在、GitHub URL から任意の MCP ツールを一発でインストールすることはできません。

現時点でサポートされている流れは次のとおりです。

1. Python パッケージをインストールする
2. Codex の `notify` と `mcp_servers` をインストール済みコマンドに向ける

このリポジトリは、その運用が分かりやすく再現可能になるように整えられています。

## インストール

### 方法 A: GitHub から `pipx` でインストール

リポジトリ URL から直接インストール:

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

### 方法 B: ローカル開発インストール

```powershell
git clone https://github.com/MarceloCaporale/codex-agent-mem.git
cd codex-agent-mem
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q
codex-agent-mem-smoke
```

## Codex の設定

そのまま貼り付けられる設定スニペットを生成:

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

このコマンドは `notify` と `[mcp_servers."codex-agent-mem"]` のブロックを出力するので、`~/.codex/config.toml` に貼り付けられます。

サンプルファイルは [examples/codex](./examples/codex/) にもあります。

## ローカル実行

検査 API を起動:

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

MCP サーバーを起動:

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

## クイック検証

Smoke テストを実行:

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

これによりサンプルのターンが挿入され、観測結果の抽出、最近の取得結果、および `project_brief` 生成が検証されます。

## リポジトリ構成

- [src/codex_agent_mem](./src/codex_agent_mem/) - パッケージコード
- [tests](./tests/) - 実行可能なテスト
- [examples/codex](./examples/codex/) - Codex 統合サンプル
- [scripts](./scripts/) - ローカル bootstrap ヘルパー
- [docs](./docs/) - アーキテクチャとリリースノート

## リリース面

このリポジトリには次が含まれます:

- クリーンなルート構成
- インストール可能な `pyproject.toml`
- コマンドエントリポイント
- テスト
- CI ワークフロー
- ライセンス
- 変更履歴
