"""マーケット情報収集エージェント（子）。

固定のカテゴリ（日本株市況・米国株市況など）ごとに「情報収集 → AI要約 →
Markdown レポート」を行う。company.py と同型のグラフ:
select_categories（対象確定）→ collect（収集・副作用はここに限定）
→ analyze（LLM要約）→ report（整形・純粋処理）。

収集ソース:
- ニュース: 共通 Web 検索ツール（topic=news）。カテゴリ単位で短期キャッシュする。
  ただし「マイポートフォリオ」（my_portfolio）はウォッチリスト・保有銘柄から
  検索クエリを都度組み立てる動的カテゴリのため、この短期キャッシュは使わない
  （Refs #80）。

対象銘柄の解決（company.py の resolve 相当）は不要（カテゴリは固定リストから
選ぶのみのため）。LLM 失敗時はルールベース要約にフォールバックし、オフラインで
も完結する。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.services.agents.runtime import invoke_llm
from app.services.agents.state import AgentState, MarketFacts, new_state
from app.services.portfolio.repository import HoldingsRepository
from app.services.screener.universe import load_universe
from app.services.search.web import SearchResult, search_web
from app.services.watchlist.repository import WatchlistRepository
from app.utils.cache import async_ttl_cache
from app.utils.settings import settings

logger = logging.getLogger(__name__)

_NEWS_PER_CATEGORY = 5

# ウォッチリスト・保有銘柄連動の動的カテゴリID（_CATEGORY_BY_ID の固定クエリを
# 使わず、_collect で個別処理する。詳細は MARKET_CATEGORIES 直前のコメント参照）。
_MY_PORTFOLIO_ID = "my_portfolio"

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


# カテゴリの実体は「検索クエリ → search_web → LLM要約」の共通パイプラインのみ
# （select_categories → collect → analyze → report）で完結する。新カテゴリの
# 追加はこのリストへのエントリ追加だけで済むように設計している（Refs #48, #74）。
#
# 例外: my_portfolio（マイポートフォリオ）はウォッチリスト・保有銘柄一覧から
# 検索クエリを実行時に組み立てる動的カテゴリで、他カテゴリと性質が異なる。
# query は構造上の一貫性のために空文字で持たせているだけで実際には使わず、
# 収集ロジック（_collect / _collect_my_portfolio）で特別扱いする（Refs #80）。
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
    {
        "id": "fx",
        "label": "為替市況",
        "query": "ドル円 為替 相場 本日の動向",
    },
    {
        "id": "semiconductor",
        "label": "半導体セクター",
        "query": "semiconductor industry news chip stocks today",
    },
    {
        "id": "my_portfolio",
        "label": "マイポートフォリオ",
        "query": "",  # 動的に組み立てるため未使用（_collect_my_portfolio で特別扱い）
    },
]

_CATEGORY_BY_ID: dict[str, dict[str, str]] = {c["id"]: c for c in MARKET_CATEGORIES}

# 「未指定 → 全カテゴリ」のデフォルト対象（my_portfolio は明示リクエスト時のみ
# 含める。ウォッチ・保有が無いユーザーにも常に薄い内容のカテゴリが生成される
# のを避けるため）。
_DEFAULT_CATEGORY_IDS = [
    c["id"] for c in MARKET_CATEGORIES if c["id"] != _MY_PORTFOLIO_ID
]


# ---------------------------------------------------------------------------
# 純粋関数（整形・ルールベース要約）
# ---------------------------------------------------------------------------


def rule_based_analysis(facts: MarketFacts) -> str:
    """LLM 不使用のルールベース要約（フォールバック。ニュース見出しの箇条書き）。"""
    if not facts["news"]:
        if facts["category"] == _MY_PORTFOLIO_ID:
            return "### 概況\n- ウォッチリスト・保有銘柄が未登録です。"
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
    elif facts["category"] == _MY_PORTFOLIO_ID:
        lines.append(
            "- ウォッチリスト・保有銘柄が未登録です"
            "（登録すると関連ニュースを表示します）"
        )
    else:
        lines.append("- 関連ニュースは取得できませんでした（検索キー未設定または0件）")
    lines += ["", "---", _DISCLAIMER]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ノード
# ---------------------------------------------------------------------------


async def _select_categories(state: AgentState) -> dict[str, Any]:
    """収集対象カテゴリを確定する（未指定・不明IDのみなら全カテゴリ）。

    my_portfolio は「未指定 → 全カテゴリ」のフォールバックには含めない
    （明示的にリクエストされた場合のみ対象にする。Refs #80）。
    """
    requested = [c for c in state["market_categories"] if c in _CATEGORY_BY_ID]
    categories = requested or _DEFAULT_CATEGORY_IDS
    return {"market_categories": categories}


@async_ttl_cache(ttl_seconds=1800)
async def _fetch_category_news(category_id: str) -> list[SearchResult]:
    """カテゴリのニュースを収集する（30分キャッシュ。検索失敗時は空リストで継続）。"""
    category = _CATEGORY_BY_ID[category_id]
    return await search_web(
        category["query"], topic="news", max_results=_NEWS_PER_CATEGORY
    )


async def _collect_one(category_id: str) -> MarketFacts:
    """1 カテゴリ分の事実情報を収集する（固定クエリのカテゴリ用）。"""
    category = _CATEGORY_BY_ID[category_id]
    news = await _fetch_category_news(category_id)
    return MarketFacts(category=category_id, label=category["label"], news=news)


async def _fetch_portfolio_codes() -> list[str]:
    """ウォッチリスト・保有銘柄コードの和集合を返す（重複除去、順序はウォッチ優先）。

    company.py の _fetch_watched_codes / _fetch_holdings と同じフォールバック
    方針（テーブル未初期化等は未登録扱いで継続）。
    """
    try:
        watched = await WatchlistRepository(settings.db_path).list_codes()
    except Exception as exc:
        logger.info("watchlist unavailable: %s", exc)
        watched = []
    try:
        holdings = await HoldingsRepository(settings.db_path).list_all()
    except Exception as exc:
        logger.info("holdings unavailable: %s", exc)
        holdings = []
    held_codes = [code for code, _quantity, _avg_cost in holdings]
    return list(dict.fromkeys(watched + held_codes))  # 順序を保った重複除去


async def _collect_my_portfolio() -> MarketFacts:
    """マイポートフォリオ（ウォッチリスト・保有銘柄連動）の事実情報を収集する。

    対象銘柄が無い場合は検索を実行せず空扱いで返す。TTLキャッシュ
    （_fetch_category_news）は使わない（ウォッチ・保有の変更を即時反映するため）。
    """
    label = _CATEGORY_BY_ID[_MY_PORTFOLIO_ID]["label"]
    codes = await _fetch_portfolio_codes()
    if not codes:
        return MarketFacts(category=_MY_PORTFOLIO_ID, label=label, news=[])

    universe = {t.code: t for t in load_universe()}
    names = [f"{universe[c].name} {c}" if c in universe else c for c in codes]
    query = ", ".join(names) + " 株価 ニュース"
    news = await search_web(query, topic="news", max_results=_NEWS_PER_CATEGORY)
    return MarketFacts(category=_MY_PORTFOLIO_ID, label=label, news=news)


async def _collect(state: AgentState) -> dict[str, Any]:
    """対象カテゴリの事実情報を収集する（副作用はこのノードに限定）。"""
    categories = state["market_categories"]
    tasks = [
        _collect_my_portfolio() if c == _MY_PORTFOLIO_ID else _collect_one(c)
        for c in categories
    ]
    facts_list = await asyncio.gather(*tasks)
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
