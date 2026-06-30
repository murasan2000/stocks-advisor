# Stocks Advisor API

FastAPI ベースのバックエンドです。東証銘柄の**株式スクリーニング**（条件絞り込み・
下がりすぎ反発検出）と、スナップショット更新ジョブを提供します。

## 開発開始

```bash
cd api
cp .env.example .env
uv sync
uv run python -m app.servers.api      # http://localhost:8000
```

mock モード（既定）では、起動時に決定論的な合成データでスナップショットを自動生成
するため、ネットワーク不要ですぐに動作確認できます。

## テスト / 静的解析

```bash
uv run pytest          # mock/合成データで実行（ネットワーク・LLM 非依存）
uv run ruff check app/
uv run mypy app/
```

## アーキテクチャ

```
servers/api.py                FastAPI エンドポイント
services/screener/
  universe.py                 銘柄ユニバース（data/tse_prime_tickers.json）読み込み
  fetcher.py                  1銘柄の取得（live=yfinance / mock=合成）
  metrics.py                  RSI・下がりすぎ反発・総合スコア（純粋関数）
  repository.py               スナップショットキャッシュ（SQLite）
  service.py                  更新（refresh）と絞り込みクエリ（staged）
services/jobs/                汎用バックグラウンドジョブ基盤（更新ジョブ・将来のエージェント用）
services/external/            Yahoo Finance クライアント / Provider / シンボル変換
services/llm, services/tracing  LLM プロバイダ・Langfuse（将来のエージェント用に温存）
```

### データ取得（snapshot キャッシュ方式）

全銘柄（約1,595）を毎回 yfinance 取得すると数分かかるため、定期的に取得した結果を
SQLite にキャッシュし、API はキャッシュから段階（stage）ごとに高速返却します。

- `EXTERNAL_API_MODE=live`: yfinance 実データ（到達不可時は合成へ自動フォールバック）
- `EXTERNAL_API_MODE=mock`: 決定論的合成データ（既定・オフライン可）

### 銘柄ユニバースの更新

同梱の `app/services/screener/data/tse_prime_tickers.json` は主要銘柄のシードです。
全銘柄へは JPX 公開リストから再生成します（JPX へ到達できる環境で実行）。

```bash
uv run --with xlrd python scripts/update_tickers.py        # プライムのみ
uv run --with xlrd python scripts/update_tickers.py --all  # 全市場
```

## 主なエンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| `GET`  | `/api/v1/screener/stocks` | 条件で絞り込んだ銘柄を stage ごとに返す（段階取得） |
| `GET`  | `/api/v1/screener/meta` | スナップショットのメタ（最終更新・件数・取得元） |
| `POST` | `/api/v1/screener/refresh` | スナップショット更新ジョブを起動 |
| `GET`  | `/api/v1/jobs/{job_id}` | ジョブの進捗・結果 |
| `GET`  | `/health` | ヘルスチェック |

### `/api/v1/screener/stocks` の主なクエリ

`stage`, `markets`（複数可）, `q`, `per_min`, `per_max`, `pbr_max`,
`dividend_yield_min`, `roe_min`, `market_cap_min`, `market_cap_max`,
`rsi_min`, `rsi_max`, `oversold`, `drop_from_high_pct`, `rebound_from_low_pct`,
`sort_by`, `sort_desc`
