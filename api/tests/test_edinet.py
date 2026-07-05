"""EDINET クライアントのテスト。"""

from __future__ import annotations

import pytest

from app.services.external import edinet
from app.services.external.edinet import (
    _match_filings,
    fetch_recent_filings,
    is_edinet_available,
)


async def test_no_api_key_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edinet.settings, "edinet_api_key", "")
    assert is_edinet_available() is False
    assert await fetch_recent_filings("7203") == []


def test_match_filings_filters_by_code_and_doc_type() -> None:
    data = {
        "results": [
            {
                "secCode": "72030",
                "docTypeCode": "120",
                "submitDateTime": "2026-06-25 09:00",
                "docDescription": "有価証券報告書－第100期",
            },
            {  # 別銘柄は除外
                "secCode": "67580",
                "docTypeCode": "120",
                "submitDateTime": "2026-06-25 09:00",
                "docDescription": "有価証券報告書",
            },
            {  # 対象外の書類種別（臨時報告書等）は除外
                "secCode": "72030",
                "docTypeCode": "180",
                "submitDateTime": "2026-06-25 09:00",
                "docDescription": "臨時報告書",
            },
        ]
    }
    assert _match_filings(data, "7203") == ["2026-06-25 有価証券報告書－第100期"]


async def test_fetch_failure_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edinet.settings, "edinet_api_key", "dummy")
    monkeypatch.setattr(edinet, "_DOCUMENTS_URL", "http://127.0.0.1:1/unreachable")
    assert await fetch_recent_filings("7203", days=1) == []
