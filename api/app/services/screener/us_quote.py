"""スクリーナー対象外（米国株）の単発quote取得。

ウォッチリスト・保有銘柄のいずれも、スクリーナースナップショットに無い
コード（米国株）の現在値をこの共通ロジックで解決する。mock時は screener と
同じ決定論的合成データを、live時はyfinanceから直接quoteを取得する
（失敗時はプレースホルダーへ縮退）。
"""

from __future__ import annotations

import asyncio
import logging

from app.services.external.symbols import to_yahoo_symbol
from app.services.screener.fetcher import fetch_live_quote, synth_row
from app.services.screener.universe import Ticker
from app.types.api import StockRow
from app.utils.cache import async_ttl_cache
from app.utils.settings import settings

logger = logging.getLogger(__name__)


def placeholder_row(code: str) -> StockRow:
    """相場を取得できないコード（上場廃止・取得失敗等）向けの最小行。"""
    return StockRow(code=code, symbol=to_yahoo_symbol(code), name=code, market="")


@async_ttl_cache(ttl_seconds=900)
async def _fetch_us_quote_live(code: str) -> StockRow:
    """米国株のライブquoteを取得する（成功時のみキャッシュする）。

    失敗時は例外を送出する（async_ttl_cacheは例外をキャッシュしないため、
    キャッシュに失敗が残らない。実際の再試行有無はfetch_live_quote側の方針
    ＝「失敗＝機能縮退」でリトライしない、に従う）。
    """
    row = await asyncio.to_thread(fetch_live_quote, code)
    if row is None:
        raise ValueError(f"no quote data for {code}")
    return row


async def fetch_us_quote(code: str) -> StockRow | None:
    """米国株のquoteを取得する（mockは決定論的合成、liveは失敗時Noneへ縮退）。"""
    if settings.external_api_mode != "live":
        return synth_row(Ticker(code=code, name=code, market="米国"))
    try:
        return await _fetch_us_quote_live(code)
    except Exception as exc:  # noqa: BLE001 - ベストエフォート（機能縮退）
        logger.info("us quote unavailable for %s: %s", code, exc)
        return None


async def fetch_us_quotes(codes: list[str]) -> dict[str, StockRow | None]:
    """複数の米国株コードのquoteを束縛付き並行取得する。

    yfinanceのレートリミット対策として、screenerの一括取得と同じ同時数に抑える。
    """
    if not codes:
        return {}
    sem = asyncio.Semaphore(settings.screener_concurrency)

    async def _bounded(code: str) -> StockRow | None:
        async with sem:
            return await fetch_us_quote(code)

    fetched = await asyncio.gather(*(_bounded(c) for c in codes))
    return dict(zip(codes, fetched, strict=True))
