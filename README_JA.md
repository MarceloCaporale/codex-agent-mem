# codex-agent-mem

他言語版: [English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md)

Codex とコーディングエージェントのワークフロー向けの、ポータブルで監査可能なローカルファースト継続性メモリレイヤー。

codex-agent-mem は、永続的なプロジェクト記憶をモデルランタイムの外に保持し、継続性をより小さな working pack に圧縮し、operational state をセッション間で持ち越します。これにより Codex は、繰り返しの少ない状態で、誤った「完了」を減らしつつ、より強いコンテキスト制御の下で作業を再開できます。

Alpha リリース。速い反復、小さなスライス、公開ベースラインを順番に積み上げる方針です。

## v0.9.0 の追加点

- 明示的な include / exclude のためのガバナンス付きメモリポリシー
- 継続性を盲目的に混ぜずに行う、プロジェクト間の選択的 inheritance
- health から導かれる repair proposal と派生 repair event
- ローカル UI とドキュメントで見える governance 状態

参照しやすいリリース: [v0.9.0 Governance](./CHANGELOG.md#090---2026-04-18) | [v0.8.0 Persistence & Observability](./CHANGELOG.md#080---2026-04-18)

## 提供するもの

### 継続性

- **生コンテキストの再送ではなく継続性の圧縮**: 生成した pack が本当に小さいときだけ `AGENTS.md` に同期
- **セッションをまたぐ operational state**: objective、constraints、pending work、blockers、Definition of Done、scope guardrails を保持
- **Codex ネイティブ統合**: `notify`、MCP stdio、自動 `AGENTS.md` 同期を前提に設計
- **実用的なトークン節約**: コンパクト pack が勝つケースでは、繰り返しコンテキストをおおむね `20%` から `55%` 削減

### Closure Control

- **決定的な closure control**: `mem_open_work` と `mem_completion_check` により、古い完了主張より未完了作業を優先
- **スコープ保持**: 決定だけでなく、recent changes、must-not-drop、blockers、アクティブな継続性も持ち越す

### ガバナンスと監査

- **ガバナンス付きメモリ選択**: policies、inheritance、repairs によって pack に入る内容を制御
- **完全ローカルかつ監査可能**: SQLite + FTS5、provenance、health、snapshots、ローカル UI を備え、外部メモリサービス不要

長時間の監査、複雑なプロジェクト継続作業、そして「決定を覚える」だけでなくスコープ喪失や早すぎる完了宣言を防ぎたいワークフロー向けです。

## 状態

`0.9.0` は現在のベースリリースです。

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
- `mem_recent_changes` による最近変更の差分取得
- `mem_scope_guard` によるスコープ継続性と must-not-drop ガード
- pending、blocker、DoD ギャップが残っているのに「完了」と言ってしまうのを防ぐ guardrail
- プロジェクト単位で closure と compression のメトリクスを永続化
- `budget=auto` のときに最小で適切な budget を自動選択
- 各 observation に対する provenance を永続化し、`mem_provenance` で取得可能
- `mem_health` によるプロジェクト健全性診断
- `mem_snapshot_create`、`mem_snapshot_list`、`mem_snapshot_restore` によるバージョン付きプロジェクトスナップショット
- `mem_policy_validate`、`mem_policy_add`、`mem_policy_list`、`mem_policy_remove` によるガバナンス付きメモリポリシー
- `mem_inheritance_add`、`mem_inheritance_list`、`mem_inheritance_remove` による選択的 inheritance リンク
- `mem_repair_propose` と `mem_repair_apply` によるガバナンス付き repair 提案と repair イベント
- FastAPI ベースの検査 API
- `/ui` で開けるローカル検査 UI。recent changes、scope guard、provenance、health、snapshots、governance 状態も表示
- ローカル policy CLI: `codex-agent-mem-policy`
- 以下を提供する MCP stdio サーバー:
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
