"""Web 検索（エージェント共通ツール）。

一般質問（Phase 6）・企業分析（Phase 7）の両エージェントが共有する。
プロバイダは Tavily（AI 向け検索・無料枠あり）。API キー未設定・失敗時は
空リストを返し、呼び出し側は「検索なし」として動作を継続する。

将来 Google Custom Search 等へ差し替える場合もこのモジュールに閉じる。
"""

from __future__ import annotations

import logging
from typing import Any, Literal, TypedDict

import httpx

from app.utils.settings import settings

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"
_TIMEOUT = 15.0

SearchTopic = Literal["general", "news"]


class SearchResult(TypedDict):
    """検索結果 1 件（引用表示に必要な最小構成）。"""

    title: str
    url: str
    snippet: str


def is_search_available() -> bool:
    """Web 検索が利用可能か（API キーが設定されているか）。"""
    return bool(settings.tavily_api_key)


async def search_web(
    query: str,
    *,
    topic: SearchTopic = "general",
    max_results: int = 5,
) -> list[SearchResult]:
    """Web 検索を実行する。キー未設定・失敗時は空リスト（検索なしで継続）。"""
    if not is_search_available():
        return []
    payload: dict[str, Any] = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "topic": topic,
        "max_results": max_results,
        "search_depth": "basic",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(_TAVILY_URL, json=payload)
            response.raise_for_status()
            data = response.json()
        return _parse_results(data, max_results)
    except Exception as exc:
        # 想定外の応答形状も含め、検索失敗は「検索なし」として継続する
        logger.warning("web search failed (topic=%s): %s", topic, exc)
        return []


def _parse_results(data: Any, max_results: int) -> list[SearchResult]:
    """Tavily 応答を SearchResult に正規化する（不正形状は上位で握る）。"""
    results: list[SearchResult] = []
    for item in data.get("results", [])[:max_results]:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=str(item.get("content") or "").strip(),
            )
        )
    return results
