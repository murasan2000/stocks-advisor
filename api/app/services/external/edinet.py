"""EDINET（金融庁の開示システム）クライアント。

企業分析エージェントが直近の開示書類（有価証券報告書・四半期/半期報告書）の
一覧を取得するために使う。EDINET API v2 は API キー（無料発行）が必要。

キー未設定・失敗時は空リストを返し、呼び出し側は「開示情報なし」で継続する。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import httpx

from app.utils.cache import async_ttl_cache
from app.utils.settings import settings

logger = logging.getLogger(__name__)

_DOCUMENTS_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
_TIMEOUT = 15.0

# 取得対象の書類種別（docTypeCode）
_DOC_TYPES = {
    "120": "有価証券報告書",
    "140": "四半期報告書",
    "160": "半期報告書",
}


def is_edinet_available() -> bool:
    """EDINET API が利用可能か（API キーが設定されているか）。"""
    return bool(settings.edinet_api_key)


def _match_filings(data: Any, sec_code: str) -> list[str]:
    """documents.json 応答から対象銘柄の開示を抽出する。"""
    filings: list[str] = []
    for doc in data.get("results", []):
        if str(doc.get("secCode") or "") != f"{sec_code}0":
            continue
        if str(doc.get("docTypeCode") or "") not in _DOC_TYPES:
            continue
        submitted = str(doc.get("submitDateTime") or "")[:10]
        description = str(doc.get("docDescription") or "開示書類")
        filings.append(f"{submitted} {description}".strip())
    return filings


@async_ttl_cache(ttl_seconds=1800)
async def fetch_recent_filings(sec_code: str, days: int = 5) -> list[str]:
    """直近 days 日分の開示書類（有報・四半期/半期）を新しい順で返す。

    キー未設定・取得失敗時は空リスト（開示なしとして継続）。
    同一銘柄への再問い合わせを抑えるため 30 分キャッシュする。
    """
    if not is_edinet_available():
        return []

    filings: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for offset in range(days):
                target = date.today() - timedelta(days=offset)
                response = await client.get(
                    _DOCUMENTS_URL,
                    params={"date": target.isoformat(), "type": 2},
                    headers={"Subscription-Key": settings.edinet_api_key},
                )
                response.raise_for_status()
                filings.extend(_match_filings(response.json(), sec_code))
    except Exception as exc:
        logger.warning("EDINET fetch failed for %s: %s", sec_code, exc)
        return []
    return filings
