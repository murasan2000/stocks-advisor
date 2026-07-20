"""米国株企業分析エージェント（子）。

日本株専用の company.py とは別モジュールとして新設する（CLAUDE.md の
「1 エージェント = 1 モジュール = 1 グラフ」「特殊分岐でなく並列モジュール化」
方針に従う）。グラフ構成は company.py と同型（resolve → collect → analyze →
report）。

収集ソース:
- 指標: yfinance のライブquote（screener.fetcher.fetch_live_quote、
  サフィックス無しでそのまま渡せる。mock時はscreenerと同じ決定論的合成データ）
- 企業概要: yfinance（EXTERNAL_API_MODE=live のみ）
- ニュース: 共通 Web 検索ツール（topic=news）

EDINET相当のデータソースは持たない（日本の開示制度のため対象外）。
MVPの対象銘柄解決はティッカー直接指定のみ（企業名からの解決は対象外）。

LLM 失敗時はルールベース分析にフォールバックし、オフラインでも完結する。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents.runtime import invoke_llm
from app.services.agents.state import AgentState, CompanyFacts, new_state
from app.services.external.symbols import to_yahoo_symbol
from app.services.screener.fetcher import fetch_live_quote, synth_row
from app.services.screener.universe import Ticker
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
    "あなたは米国株のアナリストです。与えられた事実情報（指標・企業概要・"
    "ニュース）のみに基づき、次の見出し構成の Markdown 断片を書いてください。\n"
    "### SWOT分析\n- 強み/弱み/機会/脅威 を箇条書き\n"
    "### 成長性\n- 2〜3行で評価\n"
    "### 投資判断\n- 買い/中立/売り の目安と根拠を簡潔に。断定を避けること。\n"
    "事実情報に無い内容は推測と明示し、数値を捏造しないこと。"
)


# ---------------------------------------------------------------------------
# 純粋関数（整形・ルールベース分析）
# ---------------------------------------------------------------------------


def _metrics_from_row(row: StockRow) -> dict[str, float | int | str | None]:
    """スナップショット行からレポートに使う指標を抜き出す。

    fetch_live_quote はヒストリカルを取得しないため、RSI・5年高値・
    1年安値・下落/反発率は常に None（company.py 版と異なり保持しない）。
    """
    return {
        "price": row.price,
        "change_pct": row.change_pct,
        "market_cap": row.market_cap,
        "per": row.per,
        "pbr": row.pbr,
        "dividend_yield": row.dividend_yield,
        "roe": row.roe,
        "score": row.score,
    }


def _fmt(value: float | int | str | None, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    return f"{value}{suffix}"


def _fmt_price_usd(value: float | int | str | None) -> str:
    if not isinstance(value, int | float):
        return "—"
    return f"${value:,.2f}"


def _fmt_market_cap_usd(value: float | int | str | None) -> str:
    if not isinstance(value, int | float):
        return "—"
    if value >= 999_500_000_000:
        return f"${value / 1e12:,.2f}T"
    if value >= 999_500_000:
        return f"${value / 1e9:,.1f}B"
    if value >= 999_500:
        return f"${value / 1e6:,.0f}M"
    return f"${value:,.0f}"


def rule_based_analysis(facts: CompanyFacts) -> str:
    """LLM 不使用のルールベース分析（フォールバック）。"""
    m = facts["metrics"]
    strengths: list[str] = []
    risks: list[str] = []

    per = m.get("per")
    if isinstance(per, int | float):
        if per <= 15:
            strengths.append(f"PER {per:.1f}倍と割安水準")
        elif per >= 35:
            risks.append(f"PER {per:.1f}倍と割高感")
    dividend = m.get("dividend_yield")
    if isinstance(dividend, int | float) and dividend >= 2:
        strengths.append(f"配当利回り {dividend:.2f}% と安定した株主還元")
    roe = m.get("roe")
    if isinstance(roe, int | float) and roe >= 15:
        strengths.append(f"ROE {roe:.1f}% と資本効率が良好")

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
        f"株価: {_fmt_price_usd(m.get('price'))}"
        f"（前日比 {_fmt(m.get('change_pct'), '%')}）",
        f"時価総額: {_fmt_market_cap_usd(m.get('market_cap'))}",
        f"PER: {_fmt(m.get('per'), '倍')} / PBR: {_fmt(m.get('pbr'), '倍')}"
        f" / 配当利回り: {_fmt(m.get('dividend_yield'), '%')}"
        f" / ROE: {_fmt(m.get('roe'), '%')}",
        f"総合スコア: {_fmt(m.get('score'))}/100",
    ]
    if facts["business_summary"]:
        lines += ["", f"企業概要: {facts['business_summary'][:500]}"]
    if facts["news"]:
        lines += ["", "関連ニュース:"]
        lines += [f"- {n['title']}: {n['snippet'][:150]}" for n in facts["news"]]
    return "\n".join(lines)


def build_report(facts: CompanyFacts, analysis: str) -> str:
    """1 銘柄分の Markdown レポートを組み立てる（純粋関数）。"""
    m = facts["metrics"]
    lines = [
        f"# {facts['name']}（{facts['code']}）企業分析レポート",
        "",
        "## サマリー",
        f"- 市場: {facts['market']} / 現在値 {_fmt_price_usd(m.get('price'))}"
        f"（前日比 {_fmt(m.get('change_pct'), '%')}）",
        f"- 時価総額: {_fmt_market_cap_usd(m.get('market_cap'))}"
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
    ]

    lines += ["", "## ニュース要約"]
    if facts["news"]:
        for n in facts["news"]:
            snippet = f" — {n['snippet'][:100]}" if n["snippet"] else ""
            lines.append(f"- {n['title']}{snippet}")
    else:
        lines.append("- 関連ニュースは取得できませんでした（検索キー未設定または0件）")

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
    """分析対象のティッカーを確定する。

    MVPは明示指定のみ（企業名解決は対象外）。自由記述クエリからのティッカー
    抽出は、日本株コード専用の共有ロジック（agents/resolver.py・runtime.py）
    と衝突するリスクがあるため意図的に行わない。orchestrator の委任時点
    （company/company_usへの振り分け前）で解決済みのティッカーのみを扱う、
    既知の制約（自由記述のみで米国株ティッカーだけを言及した場合は
    company_us へルーティングされない）。
    """
    return {"tickers": state["tickers"]}


@async_ttl_cache(ttl_seconds=3600)
async def _fetch_business_summary(code: str) -> str:
    """企業概要を取得する（live のみ。失敗時は空文字。1時間キャッシュ）。"""
    if settings.external_api_mode != "live":
        return ""

    def _sync() -> str:
        import yfinance as yf

        symbol = to_yahoo_symbol(code)
        info: dict[str, Any] = yf.Ticker(symbol).info or {}
        return str(info.get("longBusinessSummary") or "")

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.info("business summary unavailable for %s: %s", code, exc)
        return ""


async def _fetch_quote(code: str) -> StockRow:
    """1銘柄分のquoteを取得する（mockは決定論的合成、liveは実取得）。

    live取得に失敗した場合も合成データへフォールバックし、行を残す
    （「失敗＝機能縮退」方針。fetch_live_quote 自体もリトライしない）。
    フォールバック発生は概況ログに残す（詳細トレースはLangfuseが正）。
    """
    if settings.external_api_mode == "live":
        row = await asyncio.to_thread(fetch_live_quote, code)
        if row is not None:
            return row
        logger.info("live quote unavailable for %s, using synthetic data", code)
    return synth_row(Ticker(code=code, name=code, market="米国"))


async def _collect_one(code: str) -> CompanyFacts:
    """1 銘柄分の事実情報を収集する（quote・企業概要・ニュースを並行取得）。"""
    row, summary, news = await asyncio.gather(
        _fetch_quote(code),
        _fetch_business_summary(code),
        search_web(
            f"{code} stock earnings outlook",
            topic="news",
            max_results=_NEWS_PER_TICKER,
        ),
    )
    return CompanyFacts(
        code=code,
        name=row.name,
        market=row.market or "米国",
        metrics=_metrics_from_row(row),
        business_summary=summary,
        news=news,
        filings=[],  # EDINET相当のデータソースは持たない
    )


async def _collect(state: AgentState) -> dict[str, Any]:
    """対象銘柄の事実情報を収集する（副作用はこのノードに限定）。

    yfinanceのレートリミット対策として、screenerの一括取得と同じ同時数に抑える。
    """
    tickers = state["tickers"]
    if not tickers:
        return {"company_facts": {}}
    sem = asyncio.Semaphore(settings.screener_concurrency)

    async def _bounded(code: str) -> CompanyFacts:
        async with sem:
            return await _collect_one(code)

    facts_list = await asyncio.gather(*(_bounded(code) for code in tickers))
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
            "answer": "分析対象の米国株ティッカーを指定してください（例: AAPL）。",
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
    """米国株企業分析エージェントを単体実行し、レポート（Markdown）を返す。"""
    result = await graph.ainvoke(new_state(query, tickers), config or {})
    return str(result["answer"])
