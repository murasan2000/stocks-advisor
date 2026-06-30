"""エージェントパイプラインの状態・各エージェント出力の型定義。

MVP（Market Agent）では市場概況のみを扱う。将来エージェントを追加する際は
MultiAgentState にフィールドを足し、各エージェントの出力型を定義する。
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentError(TypedDict):
    """エージェント実行中に発生した（処理続行可能な）エラー。"""

    agent: str
    message: str


class IndexQuote(TypedDict):
    """Market Agent が取得する指数・為替の 1 項目。"""

    symbol: str  # Yahoo Finance シンボル（例: "^N225"）
    name: str  # 表示名（例: "日経平均"）
    category: str  # "index" | "fx"
    price: float
    change_pct: float  # 前日比（%）
    note: str | None  # 代理シンボル使用時の注意書きなど（UI でホバー表示）


class MarketOverview(TypedDict):
    """MarketAgent の出力（市場全体の概況）。

    設計書の Market Agent（日本株版）に対応。主要指数・為替を取得し、
    リスクオン/オフのスコアと ★1〜5 の総合評価を付与する。
    """

    indices: list[IndexQuote]
    market_trend: str  # "強気" | "中立" | "弱気"
    macro_score: float  # -1.0 〜 1.0（リスクオン/オフ）
    rating: int  # 1〜5（★の数。総合評価）
    as_of: str  # 取得日（YYYY-MM-DD）
    summary: str


class MultiAgentState(TypedDict):
    """エージェントパイプラインの共有状態。

    errors は複数エージェントから同時に追記される可能性があるため、
    operator.add で結合する。
    """

    query: str
    market: MarketOverview | None
    errors: Annotated[list[AgentError], operator.add]


def empty_state(query: str = "") -> MultiAgentState:
    """全フィールドを初期化した共有状態を生成する。

    パイプライン実行・単体エージェント実行（市場サマリー API など）で共用する。
    """
    return MultiAgentState(query=query, market=None, errors=[])
