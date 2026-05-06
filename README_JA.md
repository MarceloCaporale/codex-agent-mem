# codex-agent-mem

<p align="center">
  <img src="docs/assets/codex-agent-mem-social-preview.png" alt="codex-agent-mem: persistent local memory for MCP clients" width="100%">
</p>

他言語版: [English](./README.md) | [Español](./README_ES.md) | [Deutsch](./README_DE.md) | [Português do Brasil](./README_PT_BR.md) | [中文](./README_ZH.md)

**MCP-compatible AI agents と coding workflows 向けの、ポータブルで監査可能な local-first MCP memory。**

codex-agent-mem は、永続的なプロジェクト記憶をモデルランタイムの外に保持し、継続性をより小さな working pack に圧縮し、operational state をセッション間で持ち越します。これにより MCP-compatible AI agents は、繰り返しの少ない状態で、誤った「完了」を減らしつつ、より強いコンテキスト制御の下で作業を再開できます。

すべてはこの MCP によってローカルで保存・処理されます: SQLite database、FTS index、snapshots、telemetry metadata、任意の inspector UI。`codex-agent-mem` は memory、project data、prompts、telemetry を外部サーバーへ送信しません。MCP clients は tool results を、ユーザーが設定した model や service に見せる場合があります。そのため、retrieved memory はその client に渡される local tool output として扱ってください。

Codex と GPT workflow から生まれた `codex-agent-mem` は、いまでは Codex CLI/Desktop、Claude Code、Google Gemini CLI、Ollama models を使う Qwen Code workflows、その他の local または third-party CLI agent stacks を含む MCP-compatible runtimes 向けの portable MCP memory layer になっています。Validation は client/runtime と evidence level ごとに追跡します。Model 固有の詳細は validation docs に分離し、この README では特定 runtime を過大に主張せず public surface を説明します。

`codex-agent-mem` はローカルで動作し、memory を監査可能かつ pull-based に保ち、保存済み memory を外部サービスへ送信しません。

公開ベースライン。小さく検証可能なスライスで構築され、まだ進化中ですが、すでに実運用を意識した形です。

## v1.0.x の追加点

- v1.0.1 は、`--daemon-url` 利用時に false `Transport closed` incident として見える可能性があった local daemon / stdio bridge の idle-timeout 経路を修正します。
- v1.0.1 は、optional threaded local daemon 内の共有 request 処理を serial 化し、1 つの SQLite-backed server instance が同時に駆動されないようにします。
- v1.0.1 は public local-first daemon surface を harden します: loopback-only bind validation、`/mcp` の optional bearer-token auth、sanitized `/health`、stdio bridge からの token forwarding。
- v1.0.1 は generated context に instruction-hierarchy guardrail を追加します。取得された memory は補助的な project context であり、より高優先度の instruction ではありません。これは basic guardrail であり、prompt-injection proof ではありません。
- v1.0.1 は、public 1.0.x line の local SQLite memory が default では plaintext であり、secrets vault として扱うべきではないことを明記します。
- v1.0.1 は list を返す MCP tool payload を正規化し、`structuredContent` が root array ではなく `{items, count}` のような object root を使うようにします。これにより Claude Code など stricter clients との互換性が向上します。
- v1.0.1 は persisted memory の session-aware retrieval を追加します。`mem_session_list` で最近の session を一覧し、`mem_scope_resolve` は明示的な hint から persisted lane を順位付けし、`mem_bootstrap_context` は曖昧な container で project-wide startup pack を避け、任意の `session_id` で retrieval tools を絞り込むことで、広い project scope が chats や agents を混在させるのを避けます。複数 sessions または inferred sub-scopes をまたぐ project-wide pack は visible scope warning を出し、active context として扱う前に narrowing を推奨します。これは current turn の live awareness ではありません。
- v1.0.1 の通常の continuity install は writable です。`--read-only` は明示的な audit/debug/retrieval-only mode であり、通常の operating mode ではありません。

- 低負荷 MCP プロファイル: `minimal`、`standard`、`full`
- 変更系 tool と副作用的な書き込みを抑止する明示的な audit/debug `--read-only`
- 未使用 MCP 接続のための SQLite lazy initialization
- デフォルトでは短い MCP テキスト応答、完全な payload は `structuredContent` に保持
- 変更のない continuity pack を再送しない `known_pack_hash` / `not_modified`
- heartbeat、spawn-storm warning、任意 telemetry、任意 daemon/stdio bridge による runtime diagnostics

参照しやすいリリース: [v1.0.1 Transport + Local Security Hotfix](./CHANGELOG.md#101---prepared-2026-05-06) | [v1.0.0 Low-Impact Runtime](./CHANGELOG.md#100---2026-04-21) | [v0.9.0 Governance + Runtime Hardening](./CHANGELOG.md#090---2026-04-18)

## Snapshot (合成 v1.0 fixture)

| シナリオ | Profile | Source tokens | Pack tokens | 削減率 | `not_modified` | Tools | Lazy init | Read-only |
|---|---|---:|---:|---:|---|---:|---|---|
| Small project continuity | `minimal` | 1,841 | 253 | 86.26% | true | 4 | false->true | true |
| Medium agent workflow | `minimal` | 4,855 | 270 | 94.44% | true | 4 | false->true | true |
| Large repeated audit | `minimal` | 9,731 | 269 | 97.24% | true | 4 | false->true | true |
| Sub-agent handoff example | `minimal` | 6,523 | 276 | 95.77% | true | 4 | false->true | true |

これらの再現可能な fixture 全体では、繰り返し送られがちな operational context が約 22,950 source tokens から約 1,068 memory-pack tokens に圧縮され、約 95.35% の削減になりました。これは普遍的な保証ではなく、同じ project continuity を再送する必要があるケースでの効果を示すものです。

`Tools=4` は、これらの fixture で使った session-aware 以前の `minimal` profile を指します。v1.0.1 では `minimal` にも `mem_session_list`、`mem_scope_resolve`、`mem_bootstrap_context` が入り、`standard` profile はより広い retrieval、governance、audit workflow 向けに 20 tools を公開します。

### Runtime validation snapshot

| Runtime | 構成 | 観測された指標 | 結果 |
|---|---|---|---|
| Writable MCP default | Codex/Gemini/Claude local daemon bridges、`read_only=false`; writable tools が必要な場合は `full` | `mem_note_create` が indexed manual notes を書き込み、`mem_search` / `mem_context_pack` が回収。`mem_snapshot_create(project_key, label, session_id)` が high-confidence provenance を記録 | writable manual-note / snapshot-provenance smokes passed |
| Codex Desktop | Codex Desktop、MCP stdio、明示的な retrieval-only v1.0 fixture として `minimal`、`read-only`、`compact` | 約 22,950 source tokens -> 約 1,068 pack tokens、約 95.35% の repeated-context 削減、繰り返し pack で `not_modified=true` | retrieval-only MCP validation と公開・再現可能な検証。writable continuity は前行で検証 |
| Codex CLI / `codex exec` | Codex CLI MCP stdio path、short-lived / ephemeral execution | Desktop と同じ local MCP server / config style を使用。short-lived CLI lifecycle は long-lived Desktop host behavior とは別に検証済み | Validated Codex CLI path |
| Google Gemini CLI | `codex-agent-mem` MCP stdio、明示的な retrieval-only validation として `standard`、`read-only`; structured payload が見える場合は `compact`、見えない場合は `verbose` | プロセス安定、request counter は期待どおり増加、見える範囲で object-root payload を確認 | client exposure caveat 付き retrieval-only MCP validation |
| Claude Code | Claude Opus 4.7、`codex-agent-mem` MCP stdio のみ、明示的な retrieval-only validation として `standard`、`read-only`、`compact` | requests `3 -> 8`、lazy init `false -> true`、Claude Code host が 1 つの状態で `same_db_process_count=2`、`spawn_storm_warning=false`、`mem_search count=2` | retrieval-only MCP 検証に合格 |
| Qwen Code | Qwen Code 0.15.0、local Ollama、`qwen3.6:latest`、明示的な retrieval-only validation として `standard`、`read-only`、`compact` | `mem_context_pack`、`mem_search`、`mem_open_work`、`mem_completion_check`、`mem_health_runtime` への実 MCP call。requests `8`、lazy init `true`、`spawn_storm_warning=false`、`not_modified=true` | local retrieval-only MCP 検証に合格 |
| Qwen local model smokes | Qwen Code 0.15.0 と Ollama models `qwen3.6:35b-a3b-q8_0`、`qwen3.5:9b` | 両モデルが CLI smoke に応答し、MCP stdio 経由で `mem_health_runtime` を呼び出し。retrieval-only `read_only=true`、clean `stdin_eof` exit | local retrieval-only model smoke に合格 |
| DeepSeek-V3.2 | Qwen Code 0.15.0、Ollama Cloud 経由の `deepseek-v3.2:cloud`、明示的な retrieval-only validation として `standard`、`read-only`、`compact` | `mem_context_pack`、`mem_search`、`mem_health_runtime` への実 MCP call。requests `6`、`spawn_storm_warning=false`、`not_modified=true` | cloud-backed retrieval-only MCP 検証に合格 |
| Minimax M2.5 | Qwen Code 0.15.0、Ollama Cloud 経由の `minimax-m2.5:cloud`、明示的な retrieval-only validation として `standard`、`read-only`、`compact` | `mem_context_pack`、`mem_search`、`mem_health_runtime` への実 MCP call。requests `6`、`not_modified=true` | cloud-backed retrieval-only MCP 検証に合格 |
| Kimi Code CLI | Kimi Code CLI 1.38.0、`codex-agent-mem` MCP stdio、明示的な retrieval-only validation として `standard`、`read-only`、`compact` | `kimi mcp test codex-agent-mem` が接続し、期待される standard-profile tools を表示。Kimi K2.5 / Kimi K2.6 の model tool-call validation は continuous evaluation | retrieval-only MCP 接続は検証済み。モデル実行の検証は主張しない |
| Grok / xAI | protocol-level compatibility note | MCP stdio / JSON-RPC protocol behavior を review | protocol note |

Grok / xAI は protocol-level compatibility note として記載しており、live model tool-call validation ではありません。live validation 済みの行は、直接測定した MCP client / model pairs です: Codex Desktop/CLI、Google Gemini CLI、Claude Code、Qwen Code、Qwen local model smokes、Ollama Cloud 経由の DeepSeek-V3.2、Ollama Cloud 経由の Minimax M2.5、Kimi Code CLI connection validation。一般に `codex-agent-mem` は MCP layer では model-agnostic です。新しい pair は live measurement が取得できた時点で追加します。

## 検証可能な結果

`codex-agent-mem` には、v1.0.0 向けの再現可能な verification sandbox と公開用 evidence export が含まれています。fixture を使うのは意図的です。この MCP は repeatable operational context handling を最適化するため、公開 evidence では毎回別の会話にするのではなく、繰り返し context を制御して測定します。

公開 v1.0.x evidence は、再現可能な verification fixture と、上記 runtimes での live MCP runtime validation を組み合わせたものです。測定対象は、コンテキスト圧縮、`known_pack_hash` による再送回避、lazy initialization、最小 tool surface、明示的な read-only mode の safety、response diet、local telemetry、closure control、sub-agent handoff example です。

参照: [Verification Evidence](./docs/verification/) と [v1.0.0 Results](./docs/verification/v1.0.0/RESULTS.md)。

## Claude Code と claude-mem

`codex-agent-mem` は Claude Code で標準 MCP stdio server として動作します。session-start hook、stop hook、自動 post-turn 要約はインストールしません。メモリは `mem_context_pack`、`mem_search`、`mem_open_work`、`mem_completion_check` などの MCP tools で必要なときだけ取得します。

すでに `claude-mem` を使っている場合、両方を同時に動かすこと自体は技術的に可能です。ただし低オーバーヘッド・低レイテンシの workflow では、アクティブな memory layer は 1 つにすることを推奨します。ローカル検証では、Claude Code host が 1 つの状態で `codex-agent-mem` 単体の runtime はコンパクトでした (`same_db_process_count=2`, `spawn_storm_warning=false`)。`claude-mem` と同時に動かすと、見える tool surface は 61 tools に増え、約 6,995 tokens の session-start memory block が追加され、post-turn stop-hook の遅延が観測されました。これは `codex-agent-mem` を壊すものではありませんが、結果比較を難しくし、オーバーヘッドとレイテンシを増やす可能性があります。

local-first、監査可能、pull-based、明示的 retrieval、決定論的 closure check を重視する場合は `codex-agent-mem` を使ってください。追加の memory plugin は、その hook-based な自動動作を意図的に使いたい場合だけ有効にするのが安全です。

token に敏感な Claude Code workflow では、`codex-agent-mem` はデフォルトで軽く動くように設計されています。session-start injection なし、stop-hook summarization なし、compact response、明示的な budget、そして pack が変わらない場合の `pack_hash` / `not_modified` short-circuit を使います。

## 任意の companion: clean-process-ended

`codex-agent-mem` v1.0.1 と `clean-process-ended`（[GitHub](https://github.com/MarceloCaporale/clean-process-ended)）v0.7.2 は独立して動作しますが、local agent workflows における隣接した問題を解決します。

- `codex-agent-mem` は continuity を保持します: project memory、scoped context packs、manual notes、snapshots、open work、blockers、deterministic closure checks。
- `clean-process-ended` は local process hygiene を扱います: ownership-first diagnostics、dry-run close checks、compact janitor receipts。

組み合わせると、end-of-task workflows が改善します: context を復元し、作業を終え、local process state を確認し、compact close evidence を memory に保存できます。どちらの MCP も、もう一方の必須依存にはなりません。

## 提供するもの

### 継続性

- **生コンテキストの再送ではなく継続性の圧縮**: 生成した pack が本当に小さいときだけ `AGENTS.md` に同期
- **セッションと agents をまたぐ operational state**: objective、constraints、pending work、blockers、Definition of Done、scope guardrails を保持し、context が 1 つの model、1 つの session、1 つの provider UI に閉じ込められないようにします
- **MCP ネイティブ統合**: Codex、Claude Code、Google Gemini CLI、Qwen Code、その他 MCP-compatible clients 向けの local MCP stdio server として動作します。Codex `notify` と任意の `AGENTS.md` sync は、有用な場合にそのまま使えます
- **Agent workflows の token efficiency**: compact pack が有効な場合に continuity の再送を削減し、繰り返しの agent work における token economy を改善します。公開 v1.0 fixture では repeated-context scenario で 86% から 97% の削減を示しています

### Closure Control

- **決定的な closure control**: `mem_open_work` と `mem_completion_check` により、古い完了主張より未完了作業を優先
- **スコープ保持**: 決定だけでなく、recent changes、must-not-drop、blockers、アクティブな継続性も持ち越す

### ガバナンスと監査

- **ガバナンス付きメモリ選択**: policies、inheritance、repairs によって pack に入る内容を制御
- **検査できる MCP memory**: local `/ui` で recent changes、scope guard、provenance、health、snapshots、governance state、stored memory を閲覧でき、SQLite database を手動で開く必要がありません
- **完全ローカルかつ監査可能**: SQLite + FTS5、provenance、health、snapshots、ローカル UI を備え、外部メモリサービスや外向きの memory sync は不要
- **明確な local security boundary**: v1.0.1 は loopback daemon access、optional bearer-token auth、sanitized `/health`、generated-context instruction hierarchy を harden します。これは prompt-injection proof ではなく、public 1.0.x の SQLite database は default では plaintext であり、secrets vault として使うべきではありません

主要 docs: [AGENTS.md](./AGENTS.md) | [Quickstart](./docs/quickstart.md) | [Codex Integration](./docs/codex-integration.md) | [Codex Desktop Note](./docs/codex-desktop-lifecycle-note.md) | [Support Matrix](./docs/support-matrix.md) | [Design Decisions](./docs/design-decisions.md)

長時間の監査、複雑なプロジェクト継続作業、そして「決定を覚える」だけでなくスコープ喪失や早すぎる完了宣言を防ぎたいワークフロー向けです。

## 状態

`1.0.1` は現在の 1.0.x maintenance release です。`1.0.0` は、下記の reproducible metrics の public verification baseline として残ります。

現在動作しているもの:

- `agent-turn-complete` に対する Codex `notify` 取り込み
- FTS5 を使ったローカル SQLite 永続化
- `session_summary`、`decision`、`objective`、`constraint`、`pending_item`、`completed_item`、`blocker`、`completion_claim` のヒューリスティック抽出
- `project_dod`、`mission_dod`、`session_dod` にまたがる階層的な Definition of Done
- おおよそのトークン規模を持つコンパクトな continuity pack の生成
- `micro`、`normal`、`full` の予算付き pack
- `--sync-project-doc` を使い、pack が元のコンテキストより実際に小さい場合の `AGENTS.md` 任意同期
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
- `mem_note_create` による手動 operational note。`mem_search` で検索でき、`mem_context_pack` の対象になります
- `mem_snapshot_create`、`mem_snapshot_list`、`mem_snapshot_restore` によるバージョン付きプロジェクトスナップショット
- `mem_policy_validate`、`mem_policy_add`、`mem_policy_list`、`mem_policy_remove` によるガバナンス付きメモリポリシー
- `mem_inheritance_add`、`mem_inheritance_list`、`mem_inheritance_remove` による選択的 inheritance リンク
- `mem_repair_propose` と `mem_repair_apply` によるガバナンス付き repair 提案と repair イベント
- `--profile minimal|standard|full` による low-impact MCP profiles
- `--read-only` による明示的な read-only audit/debug mode
- full `structuredContent` を保持する compact MCP response text
- `known_pack_hash` / `not_modified` による continuity-pack reuse
- 高コスト read tools 向けの short in-process caching
- 未使用 MCP connections を安く保つ lazy SQLite initialization
- profile、mutability、cache、lazy init、heartbeat、spawn-storm diagnostics を含む enriched runtime health
- `--telemetry-mode off|summary|debug` による optional local runtime telemetry
- `codex-agent-mem-daemon` による optional local daemon と `--daemon-url` による stdio bridge mode
- FastAPI ベースの検査 API
- `/ui` で開けるローカル検査 UI。recent changes、scope guard、provenance、health、snapshots、governance 状態も表示
- ローカル policy CLI: `codex-agent-mem-policy`
- 以下を提供する MCP stdio サーバー:
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
- 自動テスト

意図的にまだ対象外としているもの:

- embeddings
- ベクターストア
- Codex App Server 取り込み
- Codex hooks アダプター
- Ollama アダプター
- マルチエージェント・オーケストレーション

## この repository が存在する理由

- Agent workflows は、単一 runtime process の外に durable context を必要とすることがあります。
- Retrieval だけでは、scope を失い user に前の context を繰り返させるという大きな failure mode を解決できません。
- Compact continuity block や MCP context pack は、手動で replay する過去 context の量を減らせます。
- Decision だけでは不十分です。runtime には active objective、open work、blockers、false closure を防ぐ rule も必要です。
- SQLite により、実装は local-first、auditable、inspectable のまま保てます。
- Current release は、広く未完成な platform ではなく、狭く testable な slice に意図的に集中しています。
- Long-lived と short-lived の MCP hosts は runtime load 下で異なる動作をすることがあります。正確な runtime boundary は validation docs を参照してください。

## インストールモデル

`codex-agent-mem` は local Python package としてインストールし、stdio command として MCP-compatible clients に公開します。

安定したパターンは次のとおりです。

1. package をインストールする
2. MCP client をインストール済み command に向ける
3. memory database を local かつ auditable に保つ

Codex 向けの `notify` と `mcp_servers` snippets は `codex-agent-mem-bootstrap-codex` が生成します。他の MCP clients はそれぞれの設定ファイルを使います。

## Quickstart

Clone から動作する local setup までの最短ルート:

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

Codex では生成された snippet を `~/.codex/config.toml` に貼り付けます。他の MCP clients では [MCP clients の設定](#mcp-clients-の設定) の common stdio command を使います。

## インストール

### 方法 A: GitHub から `pipx` でインストール

リポジトリ URL から直接インストール:

```bash
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

```powershell
pipx install "git+https://github.com/MarceloCaporale/codex-agent-mem.git"
codex-agent-mem-smoke
```

### 方法 B: ローカル開発インストール

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

## MCP clients の設定

MCP server entry point は、互換 client で共通です:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

MCP-capable client をこの installed stdio command に向けてください。public v1.0.x で検証済みの paths には Codex CLI/Desktop、Claude Code、Google Gemini CLI、Ollama 経由の local Qwen models を使う Qwen Code、Ollama Cloud 経由の DeepSeek-V3.2 と Minimax M2.5、Kimi Code CLI connection validation が含まれます。

### Codex helper

そのまま貼り付けられる設定スニペットを生成:

```bash
codex-agent-mem-bootstrap-codex --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-bootstrap-codex --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

Codex では、このコマンドが `notify`、`[mcp_servers."codex-agent-mem"]`、明示的な stdio idle timeout、そして MCP ツールの承認ブロックを出力するので、`~/.codex/config.toml` に貼り付けられます。

Long-lived Codex Desktop sessions では、`--idle-timeout-seconds 1800` のような長めの MCP idle timeout を推奨します。Desktop thread が closed stdio transport を保持しにくくなります。短い CLI や `codex exec` runs では、通常 `300` 秒で十分で、cleanup も速くなります。

自動 `AGENTS.md` 再注入も使いたい場合は、`notify` コマンドに `--sync-project-doc` を追加してください。

## エージェントでの使い方

設定後、継続性が重要な作業では、エージェントが `codex-agent-mem` を能動的に使うべきです。数ターンごとに「memory MCP を使って」と繰り返す必要はありません。

推奨パターン:

- 過去の決定、未完了作業、blocker、制約、プロジェクト状態が関係しそうなときは `mem_bootstrap_context` から始める。host が提供する場合は chat title、thread、cwd、repo hint を渡す
- scope がすでに明示的な場合だけ `mem_context_pack` を直接呼ぶ。広い workspace ではできるだけ `session_id` を使う
- 繰り返し確認するときは `known_pack_hash` を渡し、変更がない pack は文脈を再送せず `not_modified` を返す
- コンパクトな pack だけでは足りない場合にだけ `mem_search` を使う
- 実装、検証、公開、移行、ドキュメント作業で完了を主張する前に `mem_open_work` と `mem_completion_check` を呼ぶ

実用上の token economy はここから生まれます。まず小さな継続性 pack を使い、必要なときだけ詳細を展開し、変更がない同じ pack は再送しません。

サンプルファイルは [examples/codex](./examples/codex/) にあり、Ollama workflow notes は [examples/ollama](./examples/ollama/) にあります。

## ローカル実行

検査 API を起動:

```bash
codex-agent-mem-api --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-api --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

その後、ブラウザで次を開きます:

```text
http://127.0.0.1:37770/ui
```

MCP サーバーを起動:

```bash
codex-agent-mem-mcp --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-mcp --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

現在の MCP transport は stdio です。Host connection ごとに 1 process が立つのは正常であり、singleton daemon ではありません。Defensive idle timeout は未使用または orphaned な instance を clean に終了させるためのものです。

推奨 default: Codex Desktop sessions には `1800` 秒など長めの timeout、CLI/ephemeral runs には `300` 秒など短めの timeout。

1 つの directory 向けに generated continuity block を手動で再構築:

```bash
codex-agent-mem-refresh-context --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db" --project-key YOUR_PROJECT --cwd /path/to/project
```

```powershell
codex-agent-mem-refresh-context --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db --project-key YOUR_PROJECT --cwd C:\Path\To\Project
```

## クイック検証

Smoke テストを実行:

```bash
codex-agent-mem-smoke --db-path "$HOME/.codex_agent_mem/codex_agent_mem.db"
```

```powershell
codex-agent-mem-smoke --db-path C:\Users\YOU\.codex_agent_mem\codex_agent_mem.db
```

これによりサンプルのターンが挿入され、観測結果の抽出、最近の取得結果、および `project_brief` 生成が検証されます。

## Token efficiency: いま tokens を節約する仕組み

- Package は recent turns、durable decisions、derived operational state から小さな working-memory pack を作ります。
- `--sync-project-doc` が有効で、その pack が source context より本当に小さい場合、working directory の `AGENTS.md` に同期します。
- MCP retrieval と optional `AGENTS.md` sync により、future sessions は古い scope を繰り返し説明する代わりに compressed continuity から開始できます。
- `mem_context_pack` は同じ compact pack を MCP で on-demand retrieval できるようにします。
- Pack は pending work と blockers も持ち越すため、future run は「何が残っているか」を復元できます。

これは agent workflows の token efficiency であり、魔法の compression ではありません。`codex-agent-mem` は、繰り返される project context を減らし、`known_pack_hash` で unchanged packs を再利用し、agent が必要な memory だけを展開できるようにして、context の token economy を改善します。

## おおよそのトークン削減

わかりやすく言えば、これは agent にもう一度渡さなければならない重複コンテキストを減らすためのものです。完全にゼロにするわけではありませんが、かなり小さくできる場合があります。

ローカル検証から、いま正直に言えることは次のとおりです。

- 公開 v1.0 fixture では、重複コンテキストが約 22,950 source tokens から約 1,068 pack tokens へ減り、この制御されたシナリオでは約 `95.35%` の削減でした
- fixture suite の各 repeated-context scenario は `86%` から `97%` の削減でした
- live runtime check では、compact MCP retrieval、安定した process lifecycle、visible な範囲での object-root/no-reinjection behavior、local Codex/Gemini/Claude daemon bridges の writable snapshot provenance が確認されました

公開 v1.0 verification sandbox の例:

- `1,841 -> 253` おおよそのトークン
- `4,855 -> 270` おおよそのトークン
- `9,731 -> 269` おおよそのトークン
- `6,523 -> 276` おおよそのトークン

重要: これは各プロンプトごとの固定保証ではありません。生成された pack が元のコンテキストより実際に小さくない場合、`codex-agent-mem` は reinjection をスキップし、存在しない削減をあるかのようには扱いません。

## いま検出しやすくなること

- 数回の run 後に original objective を失うこと
- user が広い scope を求めたのに silent に狭めること
- pending work が残っているのに completion を宣言すること
- blockers を忘れ、次の run で task が終わったかのように再開すること

## リポジトリ構成

- [src/codex_agent_mem](./src/codex_agent_mem/) - パッケージコード
- [tests](./tests/) - 実行可能なテスト
- [examples/codex](./examples/codex/) - Codex 統合サンプル
- [examples/ollama](./examples/ollama/) - Ollama workflow notes
- [scripts](./scripts/) - ローカル bootstrap ヘルパー
- [docs](./docs/) - アーキテクチャとリリースノート

## ドキュメントマップ

- [AGENTS.md](./AGENTS.md) - MCP-compatible AI agents 向け repo map と operational guide
- [docs/quickstart.md](./docs/quickstart.md) - shortest install and first-run path
- [docs/codex-integration.md](./docs/codex-integration.md) - Codex で notify と MCP がどう合うか
- [docs/verification](./docs/verification/) - reproducible public metrics と v1.0.0 evidence
- [docs/support-matrix.md](./docs/support-matrix.md) - current support と known gaps
- [docs/codex-desktop-lifecycle-note.md](./docs/codex-desktop-lifecycle-note.md) - observed Codex Desktop lifecycle behavior と practical mitigations
- [docs/design-decisions.md](./docs/design-decisions.md) - product と architecture の explicit decisions
- [docs/architecture.md](./docs/architecture.md) - current release の portable technical architecture
- [docs/validation](./docs/validation/) - validation levels、runtime support、client behavior、public evidence notes
- [CONTRIBUTING.md](./CONTRIBUTING.md) - contribution workflow と quality bar
- [SECURITY.md](./SECURITY.md) - support scope と security reporting guidance
- [docs/discoverability.md](./docs/discoverability.md) - recommended GitHub description、topics、release framing

## リリース面

このリポジトリには次が含まれます:

- クリーンなルート構成
- インストール可能な `pyproject.toml`
- コマンドエントリポイント
- テスト
- CI ワークフロー
- ライセンス
- 変更履歴

## 作者

Marcelo Caporale が作成し、保守しています。

- X: [@MarceloCaporale](https://x.com/MarceloCaporale)
- Studio: [Visual AI Media](https://visualaimedia.com)
- Lab: [Visual Systems Lab](https://visualsystemslab.com)
