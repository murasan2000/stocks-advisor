from __future__ import annotations

from typing import Any

from app.services.analysis.indicators import (
    bollinger,
    detect_cross,
    macd,
    rsi,
    sma,
)
from app.types.agents.multi_agent import MultiAgentState, TechnicalAnalysis


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _score_to_signal(score: float) -> str:
    if score >= 0.6:
        return "強い買い"
    if score >= 0.2:
        return "買い"
    if score > -0.2:
        return "中立"
    if score > -0.6:
        return "売り"
    return "強い売り"


def _analyze(ticker: str, closes: list[float]) -> TechnicalAnalysis:
    current = closes[-1]
    sma_25 = sma(closes, 25)
    sma_75 = sma(closes, 75)
    rsi_14 = rsi(closes)
    macd_result = macd(closes)
    bb = bollinger(closes)
    cross = detect_cross(closes, 25, 75)

    score = 0.0
    if rsi_14 is not None:
        if rsi_14 < 30:
            score += 0.4  # 売られすぎ
        elif rsi_14 > 70:
            score -= 0.4  # 買われすぎ
    if sma_25 is not None:
        score += 0.2 if current > sma_25 else -0.2
    if sma_25 is not None and sma_75 is not None:
        score += 0.2 if sma_25 > sma_75 else -0.2
    if macd_result is not None:
        score += 0.2 if macd_result[2] > 0 else -0.2
    if cross == "golden":
        score += 0.4
    elif cross == "dead":
        score -= 0.4
    score = round(_clamp(score), 2)
    signal = _score_to_signal(score)

    parts = [f"シグナル: {signal}（スコア {score:+.2f}）"]
    if rsi_14 is not None:
        parts.append(f"RSI(14) {rsi_14:.1f}")
    if sma_25 is not None and sma_75 is not None:
        relation = "上" if sma_25 > sma_75 else "下"
        parts.append(f"25日線が75日線の{relation}")
    if cross == "golden":
        parts.append("直近でゴールデンクロス発生")
    elif cross == "dead":
        parts.append("直近でデッドクロス発生")

    return TechnicalAnalysis(
        ticker=ticker,
        sma_25=sma_25,
        sma_75=sma_75,
        rsi_14=rsi_14,
        macd=macd_result[0] if macd_result else None,
        macd_signal=macd_result[1] if macd_result else None,
        macd_histogram=macd_result[2] if macd_result else None,
        bb_upper=bb[0] if bb else None,
        bb_lower=bb[2] if bb else None,
        golden_cross=cross == "golden",
        dead_cross=cross == "dead",
        signal=signal,
        signal_score=score,
        summary="、".join(parts),
    )


async def technical_multi_node(state: MultiAgentState) -> dict[str, Any]:
    """市場データの過去株価からテクニカル指標とシグナルを算出する。"""
    market_data = state.get("market_data") or {}
    analysis: dict[str, TechnicalAnalysis] = {}
    for ticker, data in market_data.items():
        closes = [p.close for p in data["historical_prices"]]
        if len(closes) < 30:
            continue
        analysis[ticker] = _analyze(ticker, closes)
    return {"technical_analysis": analysis}
