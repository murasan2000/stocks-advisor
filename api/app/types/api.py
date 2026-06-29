from __future__ import annotations

from pydantic import BaseModel

from app.types.jobs import JobStatus


class StockQuery(BaseModel):
    query: str
    # Phase 3.5: 実行するエージェントの選択。
    # None / 空でフルパイプライン。前提エージェントは自動補完される。
    agents: list[str] | None = None


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class HealthResponse(BaseModel):
    status: str
    db: str
    llm_provider: str
    version: str


class IndexQuoteOut(BaseModel):
    """市場サマリーの指数・為替・金利 1 項目。"""

    symbol: str
    name: str
    category: str  # "index" | "fx" | "rate" | "volatility"
    price: float
    change_pct: float


class MarketOverviewResponse(BaseModel):
    """GET /api/v1/market/overview のレスポンス（Market Agent の出力）。"""

    indices: list[IndexQuoteOut]
    market_trend: str
    macro_score: float
    rating: int  # 1〜5（★の数）
    as_of: str
    summary: str

