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

## Git / PR ワークフロー

- 作業ブランチ: `claude/market-agent-mvp-s9yhk6`（マージ済みなら `main` から作り直す）。
- コミット/PR は指示があった時のみ。PR は draft で作成し、Issue を `Refs #N` で紐付ける。
- **自己レビュー必須**: 実装が一段落したら、ユーザーのレビューに回す前に
  `/code-review` でself-review を行い、指摘を検証・修正してから PR を提出する。
