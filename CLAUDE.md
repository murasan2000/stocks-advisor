# CLAUDE.md

Stocks Advisor（株式スクリーニング＋投資支援AIエージェント）の開発ガイド。

## プロジェクト構成

```
api/    FastAPI バックエンド（Python 3.13 / uv）
  app/servers/api.py            エンドポイント
  app/services/screener/        株式スクリーニング（yfinance + SQLite スナップショット）
  app/services/chat/            チャット履歴（会話・メッセージ）
  app/services/jobs/            汎用バックグラウンドジョブ基盤
  app/services/agents/          AI エージェント（LangGraph）
  app/services/llm/             LLM プロバイダ（Bedrock / Ollama 切替）
  app/services/tracing/         Langfuse トレーシング
  app/types/                    Pydantic / TypedDict の型定義
web/    React + TypeScript + Vite フロントエンド
db/     SQLite（.gitignore 対象）
.github/workflows/  CI（api / web で分割。詳細は「CI」節）
.claude/            権限・フックのガードレール（詳細は「ガードレール」節）
```

## 開発コマンド

バックエンド（`api/` で実行）:

```bash
uv run python -m app.servers.api   # 起動（http://localhost:8000）
uv run pytest -q                   # テスト（mock でネットワーク非依存）
uv run ruff check app/ tests/      # Lint
uv run mypy app/                   # 型チェック（strict）
```

フロントエンド（`web/` で実行）:

```bash
npm run build   # tsc + vite build
npm run lint    # eslint
npm run dev     # 開発サーバ（:5173、/api を :8000 にプロキシ）
```

- 開発時は `EXTERNAL_API_MODE=mock` で合成データを使い、ネットワーク非依存で動作確認する。
- テストは必ず mock 前提（`.env` が live でもテスト内で mock を明示）。

## コーディング規約

- Python は ruff（E/W/F/I/B/UP）+ mypy strict を通す。コメント・docstring は日本語。
- 型は Pydantic（API 境界）/ TypedDict（内部状態）を使い分ける。
- 変更は既存コードのスタイル・粒度に合わせる。

## LangGraph / LLM エージェント設計方針（重要・可読性優先）

エージェント実装はスパゲティ化しやすい。以下を必ず守る。

1. **1 エージェント = 1 モジュール = 1 グラフ**。各子エージェントは自分の
   `build_graph()` で完結し、`run()` は薄いラッパにする。共有 `BaseAgent` は作らない
   （各エージェントでノード構成が異なるため）。
2. **親と子の責務を分離**。親（orchestrator）は「意図判定 → 委任」だけを行い、
   実際の処理は子に閉じ込める。親のノードから子グラフを `ainvoke(state, config)` で呼ぶ。
3. **ノードは小さく単一責務**。1 ノード 1 目的、名前で役割が分かるようにする。
   分岐は条件関数（`route_*`）に切り出し、ノード内に埋め込まない。
4. **State は 1 箇所で定義**（`agents/state.py`）。reducer 付き TypedDict を他の
   TypedDict にネストしない（langgraph の型解決が壊れるため）。
5. **LLM アクセスは 1 つのヘルパ経由**（`agents/runtime.py` の `invoke_llm`）。
   失敗時は必ずフォールバック文字列を返し、オフライン/テストでも動くようにする。
6. **副作用（DB・ネットワーク）はノードの外か、明示した収集ノードに限定**。
   純粋な整形・判定ロジックはテスト可能な純粋関数に切り出す。
7. **トレーサビリティ**: 実行時に `RunnableConfig`（Langfuse callback 付き）を
   トップで 1 度組み立て、親 → 子へそのまま伝播させる（子 run が親 run にネストする）。
8. **応答は Job 非同期 + ポーリング**。長時間処理は `services/jobs` のジョブとして実行し、
   進捗は `AgentStep`（phase）で表現する。

## エラーハンドリング / キャッシュ / ログの方針

- **リトライは `utils/retry.py` に集約**。LLM・重要 I/O は指数バックオフ
  （`ainvoke_with_retry`）、同期処理のレートリミットは判定付き
  （`invoke_with_retry_sync(should_retry=...)`）。
- **「失敗＝機能縮退」の外部呼び出し（Web検索・EDINET 等）はリトライしない**。
  空結果を返して呼び出し側が続行する（過剰リトライで応答を遅くしない）。
- **短期キャッシュは `utils/cache.py` の `async_ttl_cache`**（企業概要 1h、
  EDINET 30min 等）。株価・指標はスクリーナーのスナップショットが正。
- **Prompt/応答の詳細トレースは Langfuse が正**（callback を親→子へ伝播）。
  アプリログは概況（所要時間・文字数・job_id）に留める。

## 開発フロー（ローカル主体）

実装はローカルの Claude Code CLI が担い、検証は GitHub Actions が Claude 抜きで
再現する、という役割分担を取る。Claude.ai の Code 機能からの指示も引き続き可能。

1. **Issue 作成**: `gh issue create`、または GitHub 上で直接。
2. **実装**: ローカル CLI が Issue を読み、この CLAUDE.md の規約に従って実装する。
3. **ローカル検証**: 下記「開発コマンド」の lint / 型チェック / テストを通す。
4. **push & PR**: `gh pr create` で draft PR を作成し、Issue を `Refs #N` で紐付ける。
5. **CI 検証**: PR をトリガーに GitHub Actions が独立して同じ検証を実行する。
6. **修正**: CI が落ちたらローカルで直して push し直す。

- **ブランチ運用・commit/push・コミットメッセージ規約は `git-workflow` skill に従う**
  （`.claude/skills/git-workflow/SKILL.md`）。要点: 作業前に必ず `claude/feature/<topic>`
  ブランチを切る、作業が一区切りついたら指示を待たずに commit + push まで行う
  （セッション切断による作業消失を防ぐため）、コミットメッセージは
  `<action>(<prefix>): <context>` 形式にする。
- **CI はローカル検証を省く理由にはしない**。CI の役割は「Claude が自分の変更を
  甘く判定していないか」を機械的に潰すことなので、両方通るのが正常な状態。
- **自己レビュー必須**: 実装が一段落したら、ユーザーのレビューに回す前に
  `/code-review` で self-review を行い、指摘を検証・修正してから PR を提出する。

## CI

`.github/workflows/` に `ci-api.yml` / `ci-web.yml` の 2 本。`main` への push と
全 PR がトリガー。実行内容はローカルの検証コマンドと同一。

- **2 本に分けている理由**: GitHub Actions の `paths` フィルタはジョブ単位では書けず
  ワークフロー単位でしか指定できないため。`api/` だけの変更で web の CI は動かない。
- **注意**: パスフィルタで実行されなかったワークフローは「成功」ではなく「未実行」に
  なる。将来ブランチ保護の必須チェックに設定する場合は、この挙動を踏まえること。
- CI 結果の確認: `gh run list --branch <branch>` / `gh run view <run-id> --log-failed`。
- **既定の `GITHUB_TOKEN` で push したコミットは CI をトリガーしない**（GitHub の
  無限ループ防止仕様）。ローカルの通常の git / gh 認証で push する限り影響はないが、
  将来 CI 側から push する仕組みを足す場合はこの制約に注意する。

## ガードレール（.claude/）

`settings.json` の permissions と、`hooks/guard-bash.py`（PreToolUse フック）で構成。
settings.json は厳密 JSON でコメントを書けないため、意図はここに記す。

- **SessionStart フック（`hooks/session-start.sh`）**: Claude Code on the web の
  リモート環境でセッション開始時に `api/`（`uv sync --group dev`）・`web/`
  （`npm install`）の依存関係を自動インストールする。ローカル（devcontainer /
  手元環境）では実行しない（`$CLAUDE_CODE_REMOTE` で判定）。ローカルは
  `.devcontainer/devcontainer.json` の `postCreateCommand`（`api/` の
  `uv sync` のみ）や開発者自身の `npm install` に任せる。これが無いと、
  リモートセッション開始直後は `web/` に `node_modules` が無く
  `npm run lint` / `npm run build` が実行できない状態になる。

- **allow**: テスト・lint・ビルド・読み取り系の git / gh など、日常的で安全なもの。
- **ask**: 外向きの操作（`git push`、`gh pr create` 等）、依存の増減（`uv add` 等）、
  および CI 定義・ガードレール自身の編集。
- **deny**: `.env` 系の読み書き、ロックファイルの直接編集、`gh secret`、force push。
- パスを対象にする権限ルールは **`Edit(...)` / `Read(...)` のみが参照される**。
  `Write(...)` で書いてもルールは無視され、起動時に警告が出るので使わないこと。
- **`ask` は毎回確認が出る**。権限プロンプトで「今後は確認しない」を選んでも、それは
  `settings.local.json` の allow として保存されるだけで、project 側の `ask` を上書き
  できない。確認が煩わしくなった項目は、この `settings.json` から外して調整する。
- **フックの担当範囲**: permissions のパターンで表現しにくいものだけ。具体的には
  フラグの書き方が複数ある force push・再帰 rm と、パスの種類で可否が変わるもの。
  `rm -rf node_modules` のようなプロジェクト内の後片付けは通し、絶対パス・ホーム・
  親ディレクトリ遡りへの再帰削除だけを止める（このため `rm` の一律 deny は置かない）。
- シェル経由の `.env` 読み取りやリダイレクト書き込みは Edit ルールの検査対象外なので、
  フック側で塞いでいる。
