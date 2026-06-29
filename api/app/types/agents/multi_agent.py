"""Phase 3 マルチエージェントの状態・各エージェント出力の型定義。

パイプライン:
    portfolio → macro → screening → market_data → (technical ‖ fundamental)
    → risk → suggestion
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.types.external.rakuten_securities import RakutenHolding
from app.types.external.yahoo_finance import OHLCV


class AgentError(TypedDict):
    """エージェント実行中に発生した（処理続行可能な）エラー。"""

    agent: str
    message: str


class PortfolioData(TypedDict):
    """PortfolioAgent の出力（楽天証券CSV解析結果）。"""

    holdings: list[RakutenHolding]
    total_market_value: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    as_of_date: str


class IndexQuote(TypedDict):
    """Market Agent が取得する指数・為替・金利の 1 項目。"""

    symbol: str  # Yahoo Finance シンボル（例: "^N225"）
    name: str  # 表示名（例: "日経平均"）
    category: str  # "index" | "fx" | "rate" | "volatility"
    price: float
    change_pct: float  # 前日比（%）


class MarketOverview(TypedDict):
    """MarketAgent の出力（市場全体の概況）。

    設計書の Market Agent に対応。主要指数・為替・金利を横断的に取得し、
    リスクオン/オフのスコアと ★1〜5 の総合評価を付与する。
    """

    indices: list[IndexQuote]
    market_trend: str  # "強気" | "中立" | "弱気"
    macro_score: float  # -1.0 〜 1.0（リスクオン/オフ）
    rating: int  # 1〜5（★の数。総合評価）
    as_of: str  # 取得日（YYYY-MM-DD）
    summary: str


class ScreeningCandidate(TypedDict):
    ticker: str  # Yahoo Finance シンボル（例: "7203.T"）
    company_name: str
    reason: str
    priority: int  # 1-5（小さいほど高優先）
    source: str  # "portfolio" | "query"


class ScreeningResult(TypedDict):
    """ScreeningAgent の出力（分析対象銘柄）。"""

    candidates: list[ScreeningCandidate]
    analysis_focus: str  # "sell" | "buy" | "hold" | "general"
    summary: str


class MarketData(TypedDict):
    """MarketDataAgent の出力（銘柄ごと）。"""

    ticker: str
    company_name: str
    current_price: float
    price_change_1d_pct: float
    volume: int
    market_cap: float | None
    fifty_two_week_high: float
    fifty_two_week_low: float
    sector: str
    historical_prices: list[OHLCV]


class TechnicalAnalysis(TypedDict):
    """TechnicalAgent の出力（銘柄ごと）。"""

    ticker: str
    sma_25: float | None
    sma_75: float | None
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bb_upper: float | None
    bb_lower: float | None
    golden_cross: bool
    dead_cross: bool
    signal: str  # "強い買い" | "買い" | "中立" | "売り" | "強い売り"
    signal_score: float  # -1.0 〜 1.0
    summary: str


class FundamentalAnalysis(TypedDict):
    """FundamentalAgent の出力（銘柄ごと）。"""

    ticker: str
    company_name: str
    fiscal_year: str
    revenue_growth_yoy: float | None  # 売上高前年比成長率（%）
    operating_margin: float  # 営業利益率（%）
    roe: float  # 自己資本利益率（%）
    per: float | None  # 株価収益率（倍）
    pbr: float | None  # 株価純資産倍率（倍）
    dividend_yield: float | None  # 配当利回り（%）
    equity_ratio: float  # 自己資本比率（%）
    valuation_score: float  # -1.0（割高）〜 1.0（割安）
    summary: str


class RiskMetrics(TypedDict):
    """銘柄ごとのリスク指標。"""

    ticker: str
    volatility_annual: float  # 年率ボラティリティ（%）
    beta: float | None  # β値（対 日経平均）
    max_drawdown: float  # 最大ドローダウン（%、負値）
    sharpe_ratio: float


class RiskAssessment(TypedDict):
    """RiskAgent の出力。"""

    portfolio_risk_score: float  # 0.0（低）〜 1.0（高）
    concentration_risk: str  # "高" | "中" | "低"
    sector_concentration: dict[str, float]  # セクター名 → 比率（%）
    individual_risks: dict[str, RiskMetrics]
    suggestions: list[str]
    summary: str


class StockSuggestion(TypedDict):
    """銘柄ごとの最終判断。"""

    ticker: str
    company_name: str
    action: str  # "強い買い" | "買い" | "中立" | "売り" | "強い売り"
    confidence: float  # 0.0 〜 1.0
    rationale: str


class SuggestionResult(TypedDict):
    """SuggestionAgent の出力（最終投資判断）。"""

    suggestions: list[StockSuggestion]
    portfolio_action: str
    risk_warnings: list[str]
    disclaimer: str


class MultiAgentState(TypedDict):
    """マルチエージェントパイプラインの共有状態。

    errors は並列ノード（technical / fundamental）から同時に追記される
    可能性があるため、operator.add で結合する。
    """

    query: str
    portfolio_data: PortfolioData | None
    market: MarketOverview | None
    screening_result: ScreeningResult | None
    market_data: dict[str, MarketData] | None
    technical_analysis: dict[str, TechnicalAnalysis] | None
    fundamental_analysis: dict[str, FundamentalAnalysis] | None
    risk_assessment: RiskAssessment | None
    final_suggestion: SuggestionResult | None
    final_answer: str | None
    errors: Annotated[list[AgentError], operator.add]


def empty_state(query: str = "") -> MultiAgentState:
    """全フィールドを初期化した共有状態を生成する。

    パイプライン実行・単体エージェント実行（市場サマリー API など）で共用する。
    """
    return MultiAgentState(
        query=query,
        portfolio_data=None,
        market=None,
        screening_result=None,
        market_data=None,
        technical_analysis=None,
        fundamental_analysis=None,
        risk_assessment=None,
        final_suggestion=None,
        final_answer=None,
        errors=[],
    )
