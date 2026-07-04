"""Web 検索ツール（共通）のテスト。"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.search import web
from app.services.search.web import SearchResult, is_search_available, search_web


async def test_no_api_key_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.settings, "tavily_api_key", "")
    assert is_search_available() is False
    assert await search_web("PERとは") == []


async def test_request_failure_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # キーは設定されているがネットワーク到達不可 → 空リストで継続
    monkeypatch.setattr(web.settings, "tavily_api_key", "dummy")
    monkeypatch.setattr(web, "_TAVILY_URL", "http://127.0.0.1:1/unreachable")
    assert await search_web("PERとは") == []


async def test_parses_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.settings, "tavily_api_key", "dummy")

    class _FakeResponse:
        def raise_for_status(self) -> None: ...

        def json(self) -> dict[str, Any]:
            return {
                "results": [
                    {"title": "PER入門", "url": "https://e.com/1", "content": "説明"},
                    {"title": "", "url": "https://e.com/skip"},  # タイトル無しは除外
                    {"title": "PBRとの違い", "url": "https://e.com/2"},
                ]
            }

    class _FakeClient:
        def __init__(self, **kwargs: Any) -> None: ...

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *args: Any) -> None: ...

        async def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:
            assert json["query"] == "PERとは"
            return _FakeResponse()

    monkeypatch.setattr(web.httpx, "AsyncClient", _FakeClient)
    results = await search_web("PERとは")
    assert results == [
        SearchResult(title="PER入門", url="https://e.com/1", snippet="説明"),
        SearchResult(title="PBRとの違い", url="https://e.com/2", snippet=""),
    ]
