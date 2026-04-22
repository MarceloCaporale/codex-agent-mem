# codex-agent-mem

他言語版: [English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [中文](./README_ZH.md)

Codex とコーディングエージェントのワークフロー向けの、ポータブルで監査可能なローカルファースト継続性メモリレイヤー。

codex-agent-mem は、永続的なプロジェクト記憶をモデルランタイムの外に保持し、継続性をより小さな working pack に圧縮し、operational state をセッション間で持ち越します。これにより Codex は、繰り返しの少ない状態で、誤った「完了」を減らしつつ、より強いコンテキスト制御の下で作業を再開できます。

すべてはこの MCP によってローカルで保存・処理されます: SQLite database、FTS index、snapshots、telemetry metadata、任意の inspector UI。`codex-agent-mem` は memory、project data、prompts、telemetry を外部サーバーへ送信しません。

`codex-agent-mem` は Codex と GPT-5.x workflow のために生まれましたが、現在は Codex CLI、Codex Desktop、Gemini 3.1 Pro を使う Gemini CLI、Opus 4.7 または Sonnet 4.6 を使う Claude Code、独自の local agent stack など、MCP-compatible agent runtime 向けの portable MCP memory layer として使えます。ローカルで動作し、memory を監査可能かつ pull-based に保ち、保存済み memory を外部サービスへ送信しません。

公開ベースライン。小さく検証可能なスライスで構築され、まだ進化中ですが、すでに実運用を意識した形です。

## v1.0.0 の追加点

- 低負荷 MCP プロファイル: `minimal`、`standard`、`full`
- 変更系 tool と副作用的な書き込みを抑止する実用的な `--read-only`
- 未使用 MCP 接続のための SQLite lazy initialization
- デフォルトでは短い MCP テキスト応答、完全な payload は `structuredContent` に保持
- 変更のない continuity pack を再送しない `known_pack_hash` / `not_modified`
- heartbeat、spawn-storm warning、任意 telemetry、任意 daemon/stdio bridge による runtime diagnostics

参照しやすいリリース: [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Snapshot

| シナリオ | Source tokens | Pack tokens | 削減率 | `not_modified` | Tools | Lazy init | Read-only |
|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | 1,841 | 216 | 88.27% | true | 4 | false->true | true |
| Medium agent workflow | 4,855 | 233 | 95.20% | true | 4 | false->true | true |
| Large repeated audit | 9,731 | 232 | 97.62% | true | 4 | false->true | true |
| Sub-agent handoff example | 6,523 | 239 | 96.34% | true | 4 | false->true | true |

これらの再現可能な fixture 全体では、繰り返し送られがちな operational context が約 22,950 source tokens から約 920 memory-pack tokens に圧縮され、約 96.0% の削減になりました。これは普遍的な保証ではなく、同じ project continuity を再送する必要があるケースでの効果を示すものです。

### Runtime validation snapshot

| Runtime | 構成 | 観測された指標 | 結果 |
|---|---|---|---|
| Codex Desktop | GPT-5.4、reasoning effort xhigh、v1.0 合成 fixture | 約 22,950 source tokens -> 約 920 pack tokens、約 96.0% の repeated-context 削減、繰り返し pack で `not_modified=true` | 公開・再現可能な検証 |
| Gemini CLI | Gemini 3.1 Pro、`codex-agent-mem` MCP stdio、`standard`、`read-only`、`compact` | プロセス安定、request counter は期待どおり増加、`mem_search` は `{items, count}` の object root と `count=2` を返却 | live MCP 検証に合格 |
| Claude Code | Claude Opus 4.7、`codex-agent-mem` MCP stdio のみ、`standard`、`read-only`、`compact` | requests `3 -> 8`、lazy init `false -> true`、`same_db_process_count=2`、`spawn_storm_warning=false`、`mem_search count=2` | live MCP 検証に合格 |

## 検証可能な結果

`codex-agent-mem` には、v1.0.0 向けの再現可能な verification sandbox と公開用 evidence export が含まれています。

現在の公開ランは、**Codex Desktop、モデル GPT-5.4、reasoning effort xhigh** で合成 fixture を使って実行されました。測定対象は、コンテキスト圧縮、`known_pack_hash` による再送回避、lazy initialization、最小 tool surface、read-only safety、response diet、local telemetry、closure control、sub-agent handoff example です。

参照: [Verification Evidence](./docs/verification/) と [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md)。

## Claude Code と claude-mem

`codex-agent-mem` は Claude Code で標準 MCP stdio server として動作します。session-start hook、stop hook、自動 post-turn 要約はインストールしません。メモリは `mem_context_pack`、`mem_search`、`mem_open_work`、`mem_completion_check` などの MCP tools で必要なときだけ取得します。

すでに `claude-mem` を使っている場合、両方を同時に動かすこと自体は技術的に可能です。ただし低レイテンシの workflow では、アクティブな memory layer は 1 つにすることを推奨します。ローカル検証では、`codex-agent-mem` 単体では runtime はコンパクトでした (`same_db_process_count=2`, `spawn_storm_warning=false`)。`claude-mem` と同時に動かすと、見える tool surface は 61 tools に増え、約 6,995 tokens の session-start memory block が追加され、post-turn stop-hook の遅延が観測されました。これは `codex-agent-mem` を壊すものではありませんが、結果比較を難しくし、レイテンシを増やす可能性があります。

local-first、監査可能、pull-based、明示的 retrieval、決定論的 closure check を重視する場合は `codex-agent-mem` を使ってください。追加の memory plugin は、その hook-based な自動動作を意図的に使いたい場合だけ有効にするのが安全です。

token に敏感な Claude Code workflow では、`codex-agent-mem` はデフォルトで軽く動くように設計されています。session-start injection なし、stop-hook summarization なし、compact response、明示的な budget、そして pack が変わらない場合の `pack_hash` / `not_modified` short-circuit を使います。

## 提供するもの

### 継続性

- **生コンテキストの再送ではなく継続性の圧縮**: 生成した pack が本当に小さいときだけ `AGENTS.md` に同期
- **セッションをまたぐ operational state**: objective、constraints、pending work、blockers、Definition of Done、scope guardrails を保持
- **Codex ネイティブ統合**: `notify`、MCP stdio、任意の `AGENTS.md` 同期、そしてより防御的なランタイム終了処理を前提に設計
- **実用的なトークン節約**: compact pack が有効な場合に continuity の再送を削減します。公開 v1.0 fixture では repeated-context scenario で 88% から 97% の削減を示しています

### Closure Control

- **決定的な closure control**: `mem_open_work` と `mem_completion_check` により、古い完了主張より未完了作業を優先
- **スコープ保持**: 決定だけでなく、recent changes、must-not-drop、blockers、アクティブな継続性も持ち越す

### ガバナンスと監査

- **ガバナンス付きメモリ選択**: policies、inheritance、repairs によって pack に入る内容を制御
- **完全ローカルかつ監査可能**: SQLite + FTS5、provenance、health、snapshots、ローカル UI を備え、外部メモリサービスや外向きの memory sync は不要

長時間の監査、複雑なプロジェクト継続作業、そして「決定を覚える」だけでなくスコープ喪失や早すぎる完了宣言を防ぎたいワークフロー向けです。

## 状態

`1.0.0` は現在のベースリリースです。

現在動作しているもの:

- `agent-turn-complete` に対する Codex `notify` 取り込み
- FTS5 を使ったローカル SQLite 永続化
- `session_summary`、`decision`、`objective`、`constraint`、`pending_item`、`completed_item`、`blocker`、`completion_claim` のヒューリスティック抽出
- `project_dod`、`mission_dod`、`session_dod` にまたがる階層的な Definition of Done
- おおよそのトークン規模を持つコンパクトな continuity pack の生成
- `micro`、`normal`、`full` の予算付き pack
- pack が元のコンテキストより実際に小さい場合の `AGENTS.md` 任意同期
- 次のセッションで目的、未完了項目、blocker、スコープガードを復元するための operational state 持ち越し
- `mem_open_work` と `mem_completion_check` による決定的な closure control
- `mem_recent_changes` による最近変更の差分取得
- `mem_scope_guard` によるスコープ継続性と must-not-drop ガード
- pending、blocker、DoD ギャップが残っているのに「完了」と言ってしまうのを防ぐ guardrail
- プロジェクト単位で closure と compression のメトリクスを永続化
- `budget=auto` のときに最小で適切な budget を自動選択
- 各 observation に対する provenance を永続化し、`mem_provenance` で取得可能
- `mem_health` によるプロジェクト健全性診断
- `mem_health_runtime` による MCP プロセスのランタイム診断
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

このコマンドは `notify`、`[mcp_servers."codex-agent-mem"]`、明示的な stdio idle timeout、そして読み取り専用 MCP ツールの承認ブロックを出力するので、`~/.codex/config.toml` に貼り付けられます。

自動 `AGENTS.md` 再注入も使いたい場合は、`notify` コマンドに `--sync-project-doc` を追加してください。

## エージェントでの使い方

設定後、継続性が重要な作業では、エージェントが `codex-agent-mem` を能動的に使うべきです。数ターンごとに「memory MCP を使って」と繰り返す必要はありません。

推奨パターン:

- 過去の決定、未完了作業、blocker、制約、プロジェクト状態が関係しそうなときは `mem_context_pack` から始める
- 繰り返し確認するときは `known_pack_hash` を渡し、変更がない pack は文脈を再送せず `not_modified` を返す
- コンパクトな pack だけでは足りない場合にだけ `mem_search` を使う
- 実装、検証、公開、移行、ドキュメント作業で完了を主張する前に `mem_open_work` と `mem_completion_check` を呼ぶ

実用上の token 節約はここから生まれます。まず小さな継続性 pack を使い、必要なときだけ詳細を展開し、変更がない同じ pack は再送しません。

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

- 公開 v1.0 fixture では、重複コンテキストが約 22,950 source tokens から約 920 pack tokens へ減り、この制御されたシナリオでは約 `96.0%` の削減でした
- fixture suite の各 repeated-context scenario は `88%` から `97%` の削減でした
- Gemini CLI と Claude Code の live runtime check では、compact MCP retrieval、安定した process lifecycle、read-only mode、object-root の `mem_search` response が確認されました

公開 v1.0 verification sandbox の例:

- `1,841 -> 216` おおよそのトークン
- `4,855 -> 233` おおよそのトークン
- `9,731 -> 232` おおよそのトークン
- `6,523 -> 239` おおよそのトークン

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
