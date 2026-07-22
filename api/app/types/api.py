from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.types.jobs import JobStatus


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class AgentJobRequest(BaseModel):
    """エージェントジョブの作成リクエスト。

    kind でエージェントを選ぶ:
      - "auto":    親エージェントが意図判定して委任
      - "general": 一般質問エージェントを直接実行（独立API）
      - "company": 企業分析エージェントを直接実行（独立API）
      - "market":  マーケット情報収集エージェントを直接実行（独立API、
                   categories未指定/不明IDのみなら全カテゴリ）
    """

    kind: Literal["auto", "general", "company", "market"] = "auto"
    query: str = Field(min_length=1, max_length=4000)
    tickers: list[str] = Field(default_factory=list)
    # kind="market" の対象カテゴリID
    categories: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    db: str
    llm_provider: str
    version: str


# ---------------------------------------------------------------------------
# スクリーナー（株式スクリーニング）
# ---------------------------------------------------------------------------


class StockRow(BaseModel):
    """スクリーニング結果の 1 銘柄。スナップショットキャッシュの 1 行に対応。"""

    code: str  # 証券コード（例: "7203", "167A"）
    symbol: str  # Yahoo Finance シンボル（例: "7203.T"）
    name: str
    market: str  # "プライム" | "スタンダード" | "グロース" | "ETF" | "REIT"
    price: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    market_cap: float | None = None
    per: float | None = None
    pbr: float | None = None
    dividend_yield: float | None = None  # %
    roe: float | None = None  # %
    rsi: float | None = None  # 14日RSI
    # 下がりすぎ反発検出用
    high_5y: float | None = None
    low_1y: float | None = None
    drop_from_high_pct: float | None = None  # 5年高値からの下落率（%, 正値）
    rebound_from_low_pct: float | None = None  # 1年安値からの反発率（%, 正値）
    score: int = 0  # 総合スコア（0〜100）


class ScreenerSummary(BaseModel):
    """絞り込み結果全体の集計（統計カード用）。"""

    count: int
    avg_per: float | None = None
    avg_dividend_yield: float | None = None
    avg_roe: float | None = None
    up: int = 0
    down: int = 0
    unchanged: int = 0


class ScreenerMeta(BaseModel):
    """スナップショットのメタ情報。"""

    last_refresh: float | None = None  # 最終更新（epoch秒）
    universe_count: int = 0  # ユニバース全銘柄数
    snapshot_count: int = 0  # キャッシュ済み銘柄数
    source: str  # "live" | "mock"


class StocksResponse(BaseModel):
    """GET /api/v1/screener/stocks のレスポンス（段階取得）。"""

    stocks: list[StockRow]
    stage: int
    next_stage: int | None  # 続きがある場合は次の stage 番号、無ければ None
    total: int  # フィルタ適用後の総件数
    summary: ScreenerSummary
    meta: ScreenerMeta


# ---------------------------------------------------------------------------
# ウォッチリスト / 銘柄詳細チャート
# ---------------------------------------------------------------------------

HistoryPeriod = Literal["3mo", "6mo", "1y", "2y", "5y", "10y"]


class Candle(BaseModel):
    """1日分の四本値・出来高。"""

    date: str  # "YYYY-MM-DD"
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockHistory(BaseModel):
    """GET /api/v1/stocks/{code}/history のレスポンス。"""

    code: str
    period: HistoryPeriod
    candles: list[Candle]


# ---------------------------------------------------------------------------
# 保有銘柄（ポートフォリオ）
# ---------------------------------------------------------------------------


class Holding(BaseModel):
    """保有銘柄の1行（スナップショット結合済み・評価損益算出済み）。"""

    code: str
    symbol: str
    name: str
    market: str
    quantity: float
    avg_cost: float
    price: float | None = None  # 現在値（スナップショット由来）
    cost_value: float  # quantity * avg_cost（取得額）
    market_value: float | None = None  # quantity * price（評価額）
    pnl: float | None = None  # market_value - cost_value（評価損益）
    pnl_pct: float | None = None  # pnl / cost_value * 100（評価損益率）


class HoldingRequest(BaseModel):
    """保有銘柄の追加/更新リクエスト。"""

    quantity: float = Field(gt=0)
    avg_cost: float = Field(gt=0)


class ImportResult(BaseModel):
    """CSVインポートの結果。"""

    imported: int  # 反映した銘柄数（重複統合後）


# ---------------------------------------------------------------------------
# マーケット情報画面
# ---------------------------------------------------------------------------


class MarketCategoryInfo(BaseModel):
    """マーケット情報のカテゴリ定義（カテゴリボックス表示用）。"""

    id: str
    label: str


class FxQuote(BaseModel):
    """為替クオート（マーケット画面・為替パネル向け）。"""

    symbol: str  # Yahoo Finance シンボル（例: "USDJPY=X"）
    label: str  # 表示名（例: "米ドル/円"）
    price: float | None = None
    change_pct: float | None = None
