# Stocks Advisor API

FastAPI ベースのバックエンドです。株式調査ジョブの作成、結果取得、市場サマリーの取得を提供します。

## 開発開始

```bash
cd api
cp .env.example .env
uv sync
uv run python -m app.servers.api
```

## テスト / 静的解析

```bash
uv run pytest          # ユニットテスト（mock/合成データで実行、ネットワーク・LLM 非依存）
uv run ruff check app/ # Lint
uv run mypy app/       # 型チェック
```

## エージェント構成

エージェントは核となる基底クラス `BaseAgent`（`app/services/agents/base.py`）を継承する。
基底クラスが「収集（collect）→ LLM 要約（fallback 付き）」の共通フローと、
LangGraph ノード化（`as_node()`）を担う。サブクラスはデータ収集と整形のみを実装する。

- `JapanMarketAgent`（`market`, `market_agent_jp.py`）: 設計書の **Market Agent**（日本株版）。
  日経平均・TOPIX・ドル円を取得し、リスクオン/オフのスコアと ★1〜5 の総合評価付きで
  市場概況を要約する。※米国株（S&P500・NASDAQ・NYダウ・VIX・米金利）は別 Issue で対応予定。

外側のパイプライン（`app/services/agents/graph/agent_selection.py`）が各エージェント
ノードを依存解決して LangGraph で実行する。

## データ取得ツール（Provider パターン）

市場データ取得は `MarketDataProvider`（`app/services/external/providers/`）に集約する。
`EXTERNAL_API_MODE` で実装を切り替える。

- `live`: `YahooFinanceProvider`（yfinance 実データ）。Yahoo 到達不可時は決定論的合成へ自動フォールバック。
- `mock`: `YahooFinanceClient`（`data/mock/` のモック、無い場合は決定論的合成）。

エージェントは `get_market_data_provider()` だけを参照するため、将来 Polygon / Finnhub /
Alpha Vantage などへ差し替える場合もこの 1 箇所で完結する。

## 主なエンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| `GET`  | `/api/v1/market/overview` | Market Agent を即時実行し市場概況（★評価付き）を返す |
| `POST` | `/api/v1/jobs` | 調査ジョブを作成（`agents` で実行エージェントを選択可） |
| `GET`  | `/api/v1/jobs/{job_id}` | ジョブのステータス・進捗・結果を取得 |
| `GET`  | `/api/v1/jobs` | 最近のジョブ一覧 |
| `GET`  | `/health` | ヘルスチェック |
