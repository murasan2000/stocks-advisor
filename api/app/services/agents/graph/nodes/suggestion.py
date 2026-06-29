from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.services.llm.provider import LLMProviderFactory
from app.types.agents.multi_agent import (
    MultiAgentState,
    StockSuggestion,
    SuggestionResult,
)
from app.utils.retry import ainvoke_with_retry

logger = logging.getLogger(__name__)

_LLM_TIMEOUT = 120.0

_DISCLAIMER = (
    "※本情報はAIによる分析であり、投資勧誘を目的としたものではありません。"
    "投資判断はご自身の責任で行ってください。"
)


def _score_to_action(score: float) -> str:
    if score >= 0.5:
        return "強い買い"
    if score >= 0.15:
        return "買い"
    if score > -0.15:
        return "中立"
    if score > -0.5:
        return "売り"
    return "強い売り"


def _build_suggestions(state: MultiAgentState) -> list[StockSuggestion]:
    """テクニカル・ファンダメンタルのスコアを統合して銘柄別判断を作る。"""
    market_data = state.get("market_data") or {}
    technical = state.get("technical_analysis") or {}
    fundamental = state.get("fundamental_analysis") or {}

    suggestions: list[StockSuggestion] = []
    for ticker, data in market_data.items():
        scores: list[float] = []
        rationale_parts: list[str] = []
        if ta := technical.get(ticker):
            scores.append(ta["signal_score"])
            rationale_parts.append(f"テクニカル: {ta['signal']}")
        if fa := fundamental.get(ticker):
            scores.append(fa["valuation_score"])
            rationale_parts.append(f"財務: スコア {fa['valuation_score']:+.2f}")
        if not scores:
            continue
        combined = sum(scores) / len(scores)
        suggestions.append(
            StockSuggestion(
                ticker=ticker,
                company_name=data["company_name"],
                action=_score_to_action(combined),
                confidence=round(min(0.9, 0.5 + abs(combined) / 2), 2),
                rationale="、".join(rationale_parts),
            )
        )
    return suggestions


def _build_context(state: MultiAgentState) -> str:
    """全エージェントの分析結果を LLM 向けにまとめる。"""
    parts: list[str] = [f"【質問】\n{state['query']}"]

    if portfolio := state.get("portfolio_data"):
        lines = [
            f"- {h['company_name']}({h['ticker']}): {h['quantity']}株、"
            f"評価額 {h['market_value']:,.0f}円、"
            f"評価損益 {h['unrealized_pnl']:+,.0f}円"
            f"（{h['unrealized_pnl_pct']:+.1f}%）"
            for h in portfolio["holdings"]
        ]
        parts.append(
            "【ポートフォリオ】\n"
            + "\n".join(lines)
            + f"\n合計評価額 {portfolio['total_market_value']:,.0f}円、"
            f"評価損益 {portfolio['total_unrealized_pnl']:+,.0f}円"
            f"（{portfolio['total_unrealized_pnl_pct']:+.1f}%）"
        )

    if macro := state.get("market"):
        parts.append(f"【市場概況】\n{macro['summary']}")

    if screening := state.get("screening_result"):
        parts.append(f"【スクリーニング】\n{screening['summary']}")

    market_data = state.get("market_data") or {}
    technical = state.get("technical_analysis") or {}
    fundamental = state.get("fundamental_analysis") or {}
    for ticker, data in market_data.items():
        lines = [
            f"現在値 {data['current_price']:,.1f}"
            f"（前日比 {data['price_change_1d_pct']:+.2f}%）、"
            f"52週レンジ {data['fifty_two_week_low']:,.1f}"
            f"〜{data['fifty_two_week_high']:,.1f}"
        ]
        if ta := technical.get(ticker):
            lines.append(ta["summary"])
        if fa := fundamental.get(ticker):
            lines.append(fa["summary"])
        parts.append(f"【{data['company_name']}（{ticker}）】\n" + "\n".join(lines))

    if risk := state.get("risk_assessment"):
        risk_lines = [risk["summary"], *risk["suggestions"]]
        parts.append("【リスク評価】\n" + "\n".join(risk_lines))

    if errors := state.get("errors"):
        lines = [f"- {e['agent']}: {e['message']}" for e in errors]
        parts.append("【取得できなかった情報】\n" + "\n".join(lines))

    return "\n\n".join(parts)


def _fallback_answer(
    state: MultiAgentState, suggestions: list[StockSuggestion]
) -> str:
    """LLM 呼び出し失敗時のルールベース回答。"""
    lines = ["## 分析結果（自動生成）", ""]
    if macro := state.get("market"):
        lines += [f"**市場概況**: {macro['summary']}", ""]
    if suggestions:
        lines.append("| 銘柄 | 判断 | 根拠 |")
        lines.append("|---|---|---|")
        lines += [
            f"| {s['company_name']}（{s['ticker']}） | {s['action']} |"
            f" {s['rationale']} |"
            for s in suggestions
        ]
        lines.append("")
    if risk := state.get("risk_assessment"):
        lines += [f"**リスク評価**: {risk['summary']}", ""]
    lines.append(_DISCLAIMER)
    return "\n".join(lines)


async def suggestion_node(
    state: MultiAgentState, config: RunnableConfig
) -> dict[str, Any]:
    """全エージェントの出力を統合し、最終投資判断レポートを生成する。"""
    suggestions = _build_suggestions(state)
    risk = state.get("risk_assessment")
    result = SuggestionResult(
        suggestions=suggestions,
        portfolio_action=(risk["suggestions"][0] if risk else ""),
        risk_warnings=(risk["suggestions"] if risk else []),
        disclaimer=_DISCLAIMER,
    )

    context = _build_context(state)
    actions = "\n".join(
        f"- {s['company_name']}（{s['ticker']}）: {s['action']}"
        f"（信頼度 {s['confidence']:.0%}、{s['rationale']}）"
        for s in suggestions
    )
    llm = LLMProviderFactory.get_llm()
    messages = [
        SystemMessage(
            content=(
                "あなたは日本株のシニア投資アドバイザーです。"
                "マルチエージェントが収集・分析した以下の情報を統合し、"
                "ユーザーの質問に Markdown 形式で回答してください。"
                "見出し・表・箇条書きを活用し、根拠を明確に述べること。"
                "最後に必ず免責事項を付けること。"
            )
        ),
        HumanMessage(
            content=(
                f"{context}\n\n"
                f"【システムによる銘柄別スコア判定】\n{actions or 'なし'}\n\n"
                "上記をもとに、質問への回答と投資判断レポートを作成してください。"
            )
        ),
    ]
    try:
        response = await ainvoke_with_retry(
            lambda: asyncio.wait_for(llm.ainvoke(messages, config), _LLM_TIMEOUT)
        )
        answer = str(response.content)
        if "免責" not in answer and "投資判断はご自身" not in answer:
            answer = f"{answer}\n\n---\n{_DISCLAIMER}"
    except Exception as exc:
        logger.error("suggestion_node LLM call failed: %s", exc, exc_info=True)
        answer = _fallback_answer(state, suggestions)

    return {"final_suggestion": result, "final_answer": answer}
