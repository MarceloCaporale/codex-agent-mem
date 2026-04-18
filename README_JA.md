# codex-agent-mem

他言語版: [English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md)

Codex とコーディングエージェントのワークフロー向けの、ポータブルでローカルファーストなメモリレイヤー。

codex-agent-mem は、エージェントの各ターンから得られた永続的な知見をローカル SQLite に保存し、MCP 経由でコンパクトな取得機能を提供します。また、メモリレイヤーを単一ベンダーのランタイム内部に隠すのではなく、監査可能でランタイム自身が管理できる状態に保ちます。

## 状態

`0.6.0` は現在の公開ベースリリースです。

現在動作しているもの:

- `agent-turn-complete` に対する Codex `notify` 取り込み
- FTS5 を使ったローカル SQLite 永続化
- `session_summary`、`decision`、`objective`、`constraint`、`pending_item`、`completed_item`、`blocker`、`completion_claim` のヒューリスティック抽出
- `project_dod`、`mission_dod`、`session_dod` にまたがる階層的な Definition of Done
- おおよそのトークン規模を持つコンパクトな continuity pack の生成
- `micro`、`normal`、`full` の予算付き pack
- pack が元のコンテキストより実際に小さい場合の `AGENTS.md` 自動同期
- 次のセッションで目的、未完了項目、blocker、スコープガードを復元するための operational state 持ち越し
- `mem_open_work` と `mem_completion_check` による決定的な closure control
- pending、blocker、DoD ギャップが残っているのに「完了」と言ってしまうのを防ぐ guardrail
- プロジェクト単位で closure と compression のメトリクスを永続化
- FastAPI ベースの検査 API
- `/ui` で開けるローカル検査 UI
- 以下を提供する MCP stdio サーバー:
  - `mem_search`
  - `mem_get`
  - `mem_recent`
  - `mem_project_brief`
  - `mem_open_work`
  - `mem_completion_check`
  - `mem_context_pack`
- 自動テスト

意図的にまだ対象外としているもの:

- embeddings
- ベクターストア
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

このコマンドは `notify`、`[mcp_servers."codex-agent-mem"]`、そして読み取り専用 MCP ツールの承認ブロックを出力するので、`~/.codex/config.toml` に貼り付けられます。

サンプルファイルは [examples/codex](./examples/codex/) にもあります。

## ローカル実行

検査 API を起動:

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

その後、ブラウザで次を開きます:

```text
http://127.0.0.1:37770/ui
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

## おおよそのトークン削減

わかりやすく言えば、これは Codex にもう一度渡さなければならない重複コンテキストを減らすためのものです。完全にゼロにするわけではありませんが、かなり小さくできる場合があります。

ローカル検証から、いま正直に言えることは次のとおりです。

- 条件が良いケースでは、コンパクト pack によって重複コンテキストが約 `20%` から `55%` 減りました
- 多くの実運用に近い実行では、だいたい `3分の1から半分程度` の重複コンテキスト削減になりました
- もし本来なら約 `1000` トークンの過去コンテキストを再送する必要がある流れなら、現実的な期待値は `450` から `800` トークン程度になることが多いです

ローカル検証の例:

- `401 -> 218` おおよそのトークン
- `312 -> 144` おおよそのトークン
- `290 -> 227` おおよそのトークン
- `337 -> 240` おおよそのトークン

重要: これは各プロンプトごとの固定保証ではありません。生成された pack が元のコンテキストより実際に小さくない場合、`codex-agent-mem` は reinjection をスキップし、存在しない削減をあるかのようには扱いません。

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
