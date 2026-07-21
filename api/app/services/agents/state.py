"""エージェント共通の状態定義（1 箇所に集約）。

全エージェント（親・子）はこの単一の State を共有する。reducer 付きフィールド
（errors）を他の TypedDict にネストしないこと（langgraph の型解決が壊れるため）。
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.services.search.web import SearchResult


class AgentError(TypedDict):
    agent: str
    message: str


class CompanyFacts(TypedDict):
    """企業分析エージェントが収集する 1 銘柄分の事実情報。

    metrics はスクリーナーのスナップショット（株価・PER・PBR・配当・ROE・RSI・
    下落/反発率・スコア等）を辞書化したもの。
    """

    code: str
    name: str
    market: str
    metrics: dict[str, float | int | str | None]
    business_summary: str  # 企業概要（live の yfinance のみ。無ければ空）
    news: list[SearchResult]  # 関連ニュース（Web検索 topic=news）
    filings: list[str]  # 直近の開示（EDINET。例: "2026-06-25 有価証券報告書"）


class MarketFacts(TypedDict):
    """マーケット情報収集エージェントが収集する 1 カテゴリ分の事実情報。"""

    category: str  # カテゴリID（例: "jp_stocks"）
    label: str  # 表示名（例: "日本株市況"）
    news: list[SearchResult]  # 関連ニュース（Web検索 topic=news）


class AgentState(TypedDict):
    """親・子エージェントで共有する状態。"""

    query: str  # ユーザーの入力
    tickers: list[str]  # 企業分析の対象銘柄（指定 or query から抽出）
    intent: str  # "general" | "company"（親が判定）
    search_results: list[SearchResult]  # Web検索の結果（引用に使う）
    company_facts: dict[str, CompanyFacts]  # 企業分析: code -> 収集済み事実
    company_analyses: dict[str, str]  # 企業分析: code -> AI分析（Markdown断片）
    # マーケット情報: 収集対象カテゴリID（未指定なら全カテゴリ）
    market_categories: list[str]
    market_facts: dict[str, MarketFacts]  # マーケット情報: category -> 収集済み事実
    # マーケット情報: category -> AI要約（Markdown断片）
    market_analyses: dict[str, str]
    answer: str  # 最終回答（Markdown）
    reports: dict[str, str]  # 企業分析/マーケット情報: code/category -> レポート
    errors: Annotated[list[AgentError], operator.add]


def new_state(
    query: str,
    tickers: list[str] | None = None,
    categories: list[str] | None = None,
) -> AgentState:
    """初期状態を生成する。"""
    return AgentState(
        query=query,
        tickers=list(tickers or []),
        intent="",
        search_results=[],
        company_facts={},
        company_analyses={},
        market_categories=list(categories or []),
        market_facts={},
        market_analyses={},
        answer="",
        reports={},
        errors=[],
    )
