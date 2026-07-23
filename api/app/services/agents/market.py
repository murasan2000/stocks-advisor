"""マーケット情報収集エージェント（子）。

固定のカテゴリ（日本株市況・米国株市況など）ごとに「情報収集 → AI要約 →
Markdown レポート」を行う。company.py と同型のグラフ:
select_categories（対象確定）→ collect（収集・副作用はここに限定）
→ analyze（LLM要約）→ report（整形・純粋処理）。

収集ソース:
- ニュース: 共通 Web 検索ツール（topic=news）。カテゴリ単位で短期キャッシュする。

対象銘柄の解決（company.py の resolve 相当）は不要（カテゴリは固定リストから
選ぶのみのため）。LLM 失敗時はルールベース要約にフォールバックし、オフラインで
も完結する。
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents.runtime import invoke_llm
from app.services.agents.state import AgentState, MarketFacts, new_state
from app.services.search.web import SearchResult, search_web
from app.utils.cache import async_ttl_cache

_NEWS_PER_CATEGORY = 5

_DISCLAIMER = (
    "※本レポートはAIによる情報収集・要約であり、投資勧誘を目的としたものではありません。"
    "投資判断はご自身の責任で行ってください。"
)

_ANALYSIS_SYSTEM_PROMPT = (
    "あなたは市況解説者です。与えられたニュース見出し・要約のみに基づき、"
    "次の見出し構成の Markdown 断片を書いてください。\n"
    "### 概況\n- 2〜3行で当日の値動き・話題を要約\n"
    "### 注目トピック\n- 箇条書きで2〜4点\n"
    "ニュースに無い内容は推測と明示し、数値を捏造しないこと。"
)


# MVPカテゴリ（固定2種）。反応を見て拡張する（Refs #48）。
MARKET_CATEGORIES: list[dict[str, str]] = [
    {
        "id": "jp_stocks",
        "label": "日本株市況",
        "query": "日本株 市況 日経平均株価 本日の値動き",
    },
    {
        "id": "us_stocks",
        "label": "米国株市況",
        "query": "US stock market today Dow Jones Nasdaq S&P 500",
    },
]

_CATEGORY_BY_ID: dict[str, dict[str, str]] = {c["id"]: c for c in MARKET_CATEGORIES}


# ---------------------------------------------------------------------------
# 純粋関数（整形・ルールベース要約）
# ---------------------------------------------------------------------------


def rule_based_analysis(facts: MarketFacts) -> str:
    """LLM 不使用のルールベース要約（フォールバック。ニュース見出しの箇条書き）。"""
    if not facts["news"]:
        return (
            "### 概況\n"
            "- 関連ニュースを取得できませんでした（検索キー未設定または0件）。"
        )
    lines = ["### 概況", "- 直近の関連ニュース見出しは以下の通りです。"]
    lines += ["", "### 注目トピック"]
    lines += [f"- {n['title']}" for n in facts["news"]]
    lines += ["", "（LLM 未接続のためルールベース簡易要約）"]
    return "\n".join(lines)


def _facts_to_prompt(facts: MarketFacts) -> str:
    """収集済み事実を LLM 要約の入力に整形する。"""
    lines = [f"カテゴリ: {facts['label']}"]
    if facts["news"]:
        lines += ["", "関連ニュース:"]
        lines += [f"- {n['title']}: {n['snippet'][:150]}" for n in facts["news"]]
    else:
        lines += ["", "関連ニュースは取得できませんでした。"]
    return "\n".join(lines)


def build_report(facts: MarketFacts, analysis: str) -> str:
    """1 カテゴリ分の Markdown レポートを組み立てる（純粋関数）。

    ニュース一覧の各項目はタイトル自体を出典へのリンクにし、末尾に別途
    「出典」セクションを設けない（同じニュースが二重に列挙されて分かりにくい
    という UI フィードバックを踏まえた設計）。
    """
    lines = [f"# {facts['label']}", "", analysis, "", "## ニュース一覧"]
    if facts["news"]:
        for n in facts["news"]:
            snippet = f" — {n['snippet'][:100]}" if n["snippet"] else ""
            lines.append(f"- [{n['title']}]({n['url']}){snippet}")
    else:
        lines.append("- 関連ニュースは取得できませんでした（検索キー未設定または0件）")
    lines += ["", "---", _DISCLAIMER]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ノード
# ---------------------------------------------------------------------------


async def _select_categories(state: AgentState) -> dict[str, Any]:
    """収集対象カテゴリを確定する（未指定・不明IDのみなら全カテゴリ）。"""
    requested = [c for c in state["market_categories"] if c in _CATEGORY_BY_ID]
    categories = requested or [c["id"] for c in MARKET_CATEGORIES]
    return {"market_categories": categories}


@async_ttl_cache(ttl_seconds=1800)
async def _fetch_category_news(category_id: str) -> list[SearchResult]:
    """カテゴリのニュースを収集する（30分キャッシュ。検索失敗時は空リストで継続）。"""
    category = _CATEGORY_BY_ID[category_id]
    return await search_web(
        category["query"], topic="news", max_results=_NEWS_PER_CATEGORY
    )


async def _collect_one(category_id: str) -> MarketFacts:
    """1 カテゴリ分の事実情報を収集する。"""
    category = _CATEGORY_BY_ID[category_id]
    news = await _fetch_category_news(category_id)
    return MarketFacts(category=category_id, label=category["label"], news=news)


async def _collect(state: AgentState) -> dict[str, Any]:
    """対象カテゴリの事実情報を収集する（副作用はこのノードに限定）。"""
    categories = state["market_categories"]
    facts_list = await asyncio.gather(*(_collect_one(c) for c in categories))
    return {"market_facts": {f["category"]: f for f in facts_list}}


async def _analyze(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """収集済み事実をもとに LLM で要約する（失敗時はルールベース）。"""
    analyses: dict[str, str] = {}
    for category_id, facts in state["market_facts"].items():
        analyses[category_id] = await invoke_llm(
            _ANALYSIS_SYSTEM_PROMPT,
            _facts_to_prompt(facts),
            fallback=rule_based_analysis(facts),
            config=config,
        )
    return {"market_analyses": analyses}


async def _report(state: AgentState) -> dict[str, Any]:
    """カテゴリごとの Markdown レポートを組み立てる。"""
    facts_map = state["market_facts"]
    if not facts_map:
        return {"answer": "収集対象のカテゴリがありません。", "reports": {}}
    reports = {
        category_id: build_report(facts, state["market_analyses"].get(category_id, ""))
        for category_id, facts in facts_map.items()
    }
    answer = "\n\n---\n\n".join(reports[c] for c in facts_map)
    return {"reports": reports, "answer": answer}


def build_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("select_categories", _select_categories)
    builder.add_node("collect", _collect)
    builder.add_node("analyze", _analyze)
    builder.add_node("report", _report)
    builder.add_edge(START, "select_categories")
    builder.add_edge("select_categories", "collect")
    builder.add_edge("collect", "analyze")
    builder.add_edge("analyze", "report")
    builder.add_edge("report", END)
    return builder.compile()


graph = build_graph()


async def run(
    categories: list[str] | None = None,
    config: RunnableConfig | None = None,
) -> str:
    """マーケット情報収集エージェントを単体実行し、レポート（Markdown）を返す。"""
    result = await graph.ainvoke(new_state("", categories=categories), config or {})
    return str(result["answer"])
