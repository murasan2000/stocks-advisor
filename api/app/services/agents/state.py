"""エージェント共通の状態定義（1 箇所に集約）。

全エージェント（親・子）はこの単一の State を共有する。reducer 付きフィールド
（errors）を他の TypedDict にネストしないこと（langgraph の型解決が壊れるため）。
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentError(TypedDict):
    agent: str
    message: str


class AgentState(TypedDict):
    """親・子エージェントで共有する状態。"""

    query: str  # ユーザーの入力
    tickers: list[str]  # 企業分析の対象銘柄（指定 or query から抽出）
    intent: str  # "general" | "company"（親が判定）
    answer: str  # 最終回答（Markdown）
    reports: dict[str, str]  # 企業分析: ticker -> レポート
    errors: Annotated[list[AgentError], operator.add]


def new_state(query: str, tickers: list[str] | None = None) -> AgentState:
    """初期状態を生成する。"""
    return AgentState(
        query=query,
        tickers=list(tickers or []),
        intent="",
        answer="",
        reports={},
        errors=[],
    )
