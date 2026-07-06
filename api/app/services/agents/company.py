"""企業分析エージェント（子）。

対象銘柄ごとに「情報収集 → AI分析 → Markdown レポート」を行う。
グラフ: resolve（対象確定）→ collect（収集・副作用はここに限定）
       → analyze（LLM 分析）→ report（整形・純粋処理）

収集ソース:
- 指標: スクリーナーのスナップショット（無ければ決定論的合成にフォールバック）
- 企業概要: yfinance（EXTERNAL_API_MODE=live のみ）
- ニュース: 共通 Web 検索ツール（topic=news）
- 開示: EDINET（キー設定時のみ）

LLM 失敗時はルールベース分析にフォールバックし、オフラインでも完結する。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents.resolver import resolve_tickers
from app.services.agents.runtime import invoke_llm
from app.services.agents.state import AgentState, CompanyFacts, new_state
from app.services.external.edinet import fetch_recent_filings
from app.services.screener.fetcher import synth_row
from app.services.screener.repository import ScreenerRepository
from app.services.screener.universe import Ticker, load_universe
from app.services.search.web import search_web
from app.types.api import StockRow
from app.utils.cache import async_ttl_cache
from app.utils.settings import settings

logger = logging.getLogger(__name__)

_NEWS_PER_TICKER = 3

_DISCLAIMER = (
    "※本レポートはAIによる分析であり、投資勧誘を目的としたものではありません。"
    "投資判断はご自身の責任で行ってください。"
)

_ANALYSIS_SYSTEM_PROMPT = (
    "あなたは日本株のアナリストです。与えられた事実情報（指標・企業概要・"
    "ニュース・開示）のみに基づき、次の見出し構成の Markdown 断片を書いてください。\n"
    "### SWOT分析\n- 強み/弱み/機会/脅威 を箇条書き\n"
    "### 成長性\n- 2〜3行で評価\n"
    "### 投資判断\n- 買い/中立/売り の目安と根拠を簡潔に。断定を避けること。\n"
    "事実情報に無い内容は推測と明示し、数値を捏造しないこと。"
)


# ---------------------------------------------------------------------------
# 純粋関数（整形・ルールベース分析）
# ---------------------------------------------------------------------------


def _metrics_from_row(row: StockRow) -> dict[str, float | int | str | None]:
    """スナップショット行からレポートに使う指標を抜き出す。"""
    return {
        "price": row.price,
        "change_pct": row.change_pct,
        "market_cap": row.market_cap,
        "per": row.per,
        "pbr": row.pbr,
        "dividend_yield": row.dividend_yield,
        "roe": row.roe,
        "rsi": row.rsi,
        "high_5y": row.high_5y,
        "low_1y": row.low_1y,
        "drop_from_high_pct": row.drop_from_high_pct,
        "rebound_from_low_pct": row.rebound_from_low_pct,
        "score": row.score,
    }


def _fmt(value: float | int | str | None, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    return f"{value}{suffix}"


def _fmt_market_cap(value: float | int | str | None) -> str:
    if not isinstance(value, int | float):
        return "—"
    if value >= 1e12:
        return f"{value / 1e12:,.2f}兆円"
    if value >= 1e8:
        return f"{value / 1e8:,.0f}億円"
    return f"{value:,.0f}円"


def rule_based_analysis(facts: CompanyFacts) -> str:
    """LLM 不使用のルールベース分析（フォールバック）。"""
    m = facts["metrics"]
    strengths: list[str] = []
    risks: list[str] = []

    per = m.get("per")
    if isinstance(per, int | float):
        if per <= 12:
            strengths.append(f"PER {per:.1f}倍と割安水準")
        elif per >= 25:
            risks.append(f"PER {per:.1f}倍と割高感")
    dividend = m.get("dividend_yield")
    if isinstance(dividend, int | float) and dividend >= 3:
        strengths.append(f"配当利回り {dividend:.2f}% と高配当")
    roe = m.get("roe")
    if isinstance(roe, int | float) and roe >= 10:
        strengths.append(f"ROE {roe:.1f}% と資本効率が良好")
    rsi = m.get("rsi")
    if isinstance(rsi, int | float):
        if rsi >= 70:
            risks.append(f"RSI {rsi:.0f} と短期的な過熱感")
        elif rsi <= 30:
            strengths.append(f"RSI {rsi:.0f} と売られすぎ水準")
    drop = m.get("drop_from_high_pct")
    if isinstance(drop, int | float) and drop >= 50:
        risks.append(f"5年高値から {drop:.0f}% 下落（長期下落トレンド）")

    score = m.get("score")
    if isinstance(score, int | float):
        if score >= 70:
            judgement = "買い検討（スコア高位）"
        elif score >= 45:
            judgement = "中立（材料の見極めを推奨）"
        else:
            judgement = "慎重（弱い指標が目立つ）"
        judgement += f" — 総合スコア {score:.0f}/100"
    else:
        judgement = "判断材料不足"

    lines = ["### SWOT分析"]
    lines += [f"- 強み: {s}" for s in strengths] or ["- 強み: 特筆事項なし"]
    lines += [f"- リスク: {r}" for r in risks] or ["- リスク: 特筆事項なし"]
    lines += ["", "### 投資判断", f"- {judgement}"]
    lines += ["", "（LLM 未接続のためルールベース簡易分析）"]
    return "\n".join(lines)


def _facts_to_prompt(facts: CompanyFacts) -> str:
    """収集済み事実を LLM 分析の入力に整形する。"""
    m = facts["metrics"]
    lines = [
        f"銘柄: {facts['name']}（{facts['code']} / {facts['market']}）",
        f"株価: {_fmt(m.get('price'), '円')}"
        f"（前日比 {_fmt(m.get('change_pct'), '%')}）",
        f"時価総額: {_fmt_market_cap(m.get('market_cap'))}",
        f"PER: {_fmt(m.get('per'), '倍')} / PBR: {_fmt(m.get('pbr'), '倍')}"
        f" / 配当利回り: {_fmt(m.get('dividend_yield'), '%')}"
        f" / ROE: {_fmt(m.get('roe'), '%')}",
        f"RSI(14): {_fmt(m.get('rsi'))} / 総合スコア: {_fmt(m.get('score'))}/100",
        f"5年高値からの下落率: {_fmt(m.get('drop_from_high_pct'), '%')}"
        f" / 1年安値からの反発率: {_fmt(m.get('rebound_from_low_pct'), '%')}",
    ]
    if facts["business_summary"]:
        lines += ["", f"企業概要: {facts['business_summary'][:500]}"]
    if facts["news"]:
        lines += ["", "関連ニュース:"]
        lines += [f"- {n['title']}: {n['snippet'][:150]}" for n in facts["news"]]
    if facts["filings"]:
        lines += ["", "直近の開示:"]
        lines += [f"- {f}" for f in facts["filings"]]
    return "\n".join(lines)


def build_report(facts: CompanyFacts, analysis: str) -> str:
    """1 銘柄分の Markdown レポートを組み立てる（純粋関数）。"""
    m = facts["metrics"]
    lines = [
        f"# {facts['name']}（{facts['code']}）企業分析レポート",
        "",
        "## サマリー",
        f"- 市場: {facts['market']} / 現在値 {_fmt(m.get('price'), '円')}"
        f"（前日比 {_fmt(m.get('change_pct'), '%')}）",
        f"- 時価総額: {_fmt_market_cap(m.get('market_cap'))}"
        f" / 総合スコア: {_fmt(m.get('score'))}/100",
    ]
    if facts["business_summary"]:
        lines.append(f"- 概要: {facts['business_summary'][:200]}")
    lines += [
        "",
        "## 財務分析",
        "| 指標 | 値 |",
        "|---|---|",
        f"| PER | {_fmt(m.get('per'), '倍')} |",
        f"| PBR | {_fmt(m.get('pbr'), '倍')} |",
        f"| 配当利回り | {_fmt(m.get('dividend_yield'), '%')} |",
        f"| ROE | {_fmt(m.get('roe'), '%')} |",
        f"| RSI(14) | {_fmt(m.get('rsi'))} |",
        f"| 5年高値からの下落率 | {_fmt(m.get('drop_from_high_pct'), '%')} |",
        f"| 1年安値からの反発率 | {_fmt(m.get('rebound_from_low_pct'), '%')} |",
    ]

    lines += ["", "## ニュース要約"]
    if facts["news"]:
        for n in facts["news"]:
            snippet = f" — {n['snippet'][:100]}" if n["snippet"] else ""
            lines.append(f"- {n['title']}{snippet}")
    else:
        lines.append("- 関連ニュースは取得できませんでした（検索キー未設定または0件）")

    if facts["filings"]:
        lines += ["", "## 直近の開示（EDINET）"]
        lines += [f"- {f}" for f in facts["filings"]]

    lines += ["", "## AI評価", analysis]

    lines += ["", "## 総評"]
    score = m.get("score")
    if isinstance(score, int | float):
        lines.append(
            f"総合スコア {score:.0f}/100。詳細は AI 評価・財務分析を参照してください。"
        )
    else:
        lines.append("判断材料が不足しています。")
    lines += ["", "---", _DISCLAIMER]

    if facts["news"]:
        lines += ["", "#### 出典"]
        lines += [
            f"{i}. [{n['title']}]({n['url']})"
            for i, n in enumerate(facts["news"], start=1)
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ノード
# ---------------------------------------------------------------------------


async def _resolve(state: AgentState) -> dict[str, Any]:
    """分析対象の銘柄を確定する（未指定なら query のコード・企業名から解決）。"""
    tickers = state["tickers"] or resolve_tickers(state["query"])
    return {"tickers": tickers}


@async_ttl_cache(ttl_seconds=3600)
async def _fetch_business_summary(code: str) -> str:
    """企業概要を取得する（live のみ。失敗時は空文字。1時間キャッシュ）。"""
    if settings.external_api_mode != "live":
        return ""

    def _sync() -> str:
        import yfinance as yf

        info: dict[str, Any] = yf.Ticker(f"{code}.T").info or {}
        return str(info.get("longBusinessSummary") or "")

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.info("business summary unavailable for %s: %s", code, exc)
        return ""


async def _collect_one(code: str, row: StockRow | None) -> CompanyFacts:
    """1 銘柄分の事実情報を収集する。"""
    universe = {t.code: t for t in load_universe()}
    ticker = universe.get(code) or Ticker(code=code, name=code, market="不明")
    if row is None:
        row = synth_row(ticker)  # スナップショット未取得時の決定論的フォールバック

    summary, news, filings = await asyncio.gather(
        _fetch_business_summary(code),
        search_web(
            f"{ticker.name} 株 業績", topic="news", max_results=_NEWS_PER_TICKER
        ),
        fetch_recent_filings(code),
    )
    return CompanyFacts(
        code=code,
        name=row.name if row.name != code else ticker.name,
        market=ticker.market,
        metrics=_metrics_from_row(row),
        business_summary=summary,
        news=news,
        filings=filings,
    )


async def _collect(state: AgentState) -> dict[str, Any]:
    """対象銘柄の事実情報を収集する（副作用はこのノードに限定）。"""
    tickers = state["tickers"]
    if not tickers:
        return {"company_facts": {}}

    try:
        snapshot = await ScreenerRepository(settings.db_path).get_all()
    except Exception as exc:  # テーブル未初期化等 → 合成フォールバックで継続
        logger.info("screener snapshot unavailable: %s", exc)
        snapshot = []
    by_code = {r.code: r for r in snapshot}
    facts_list = await asyncio.gather(
        *(_collect_one(code, by_code.get(code)) for code in tickers)
    )
    return {"company_facts": {f["code"]: f for f in facts_list}}


async def _analyze(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """収集済み事実をもとに LLM で分析する（失敗時はルールベース）。"""
    analyses: dict[str, str] = {}
    for code, facts in state["company_facts"].items():
        analyses[code] = await invoke_llm(
            _ANALYSIS_SYSTEM_PROMPT,
            _facts_to_prompt(facts),
            fallback=rule_based_analysis(facts),
            config=config,
        )
    return {"company_analyses": analyses}


async def _report(state: AgentState) -> dict[str, Any]:
    """銘柄ごとの Markdown レポートを組み立てる。"""
    facts_map = state["company_facts"]
    if not facts_map:
        return {
            "answer": "分析対象の銘柄コードを指定してください（例: 7203）。",
            "reports": {},
        }
    reports = {
        code: build_report(facts, state["company_analyses"].get(code, ""))
        for code, facts in facts_map.items()
    }
    answer = "\n\n---\n\n".join(reports[code] for code in facts_map)
    return {"reports": reports, "answer": answer}


def build_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("resolve", _resolve)
    builder.add_node("collect", _collect)
    builder.add_node("analyze", _analyze)
    builder.add_node("report", _report)
    builder.add_edge(START, "resolve")
    builder.add_edge("resolve", "collect")
    builder.add_edge("collect", "analyze")
    builder.add_edge("analyze", "report")
    builder.add_edge("report", END)
    return builder.compile()


graph = build_graph()


async def run(
    query: str,
    tickers: list[str] | None = None,
    config: RunnableConfig | None = None,
) -> str:
    """企業分析エージェントを単体実行し、レポート（Markdown）を返す。"""
    result = await graph.ainvoke(new_state(query, tickers), config or {})
    return str(result["answer"])
