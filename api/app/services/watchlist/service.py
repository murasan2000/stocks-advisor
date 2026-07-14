"""ウォッチリストのユースケース: 登録コードとスナップショットの結合。

日本株はスクリーナーのスナップショットと結合する（従来通り）。米国株
（スクリーナー対象外）はスナップショットに存在しないため、mock時は
screenerと同じ決定論的合成データを、live時はyfinanceから直接quoteを
取得する（失敗時はプレースホルダーへ縮退）。
"""

from __future__ import annotations

import asyncio
import logging

from app.services.external.symbols import to_yahoo_symbol
from app.services.screener.fetcher import fetch_live_quote, synth_row
from app.services.screener.repository import ScreenerRepository
from app.services.screener.universe import Ticker
from app.services.watchlist.repository import WatchlistRepository
from app.types.api import StockRow
from app.utils.cache import async_ttl_cache
from app.utils.market import is_jp_code
from app.utils.settings import settings

logger = logging.getLogger(__name__)


def _placeholder_row(code: str) -> StockRow:
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


async def _fetch_us_quote(code: str) -> StockRow | None:
    """米国株のquoteを取得する（mockは決定論的合成、liveは失敗時Noneへ縮退）。"""
    if settings.external_api_mode != "live":
        return synth_row(Ticker(code=code, name=code, market="米国"))
    try:
        return await _fetch_us_quote_live(code)
    except Exception as exc:  # noqa: BLE001 - ベストエフォート（機能縮退）
        logger.info("us quote unavailable for %s: %s", code, exc)
        return None


class WatchlistService:
    def __init__(
        self, repo: WatchlistRepository, screener_repo: ScreenerRepository
    ) -> None:
        self._repo = repo
        self._screener_repo = screener_repo

    async def add(self, code: str) -> None:
        await self._repo.add(code)

    async def remove(self, code: str) -> None:
        await self._repo.remove(code)

    async def list_codes(self) -> list[str]:
        return await self._repo.list_codes()

    async def list_rows(self) -> list[StockRow]:
        """登録順（新しい順）でスナップショット結合済みの行を返す。

        スナップショットに無い日本株コードはプレースホルダー、米国株コードは
        quote取得（mockは合成データ、liveは実際の取得）を試み、live取得の
        失敗時のみプレースホルダーへ縮退する。
        """
        codes = await self._repo.list_codes()
        if not codes:
            return []
        snapshot = {r.code: r for r in await self._screener_repo.get_by_codes(codes)}
        missing_us = [c for c in codes if c not in snapshot and not is_jp_code(c)]
        # yfinanceのレートリミット対策として、screenerの一括取得と同じ同時数に抑える。
        sem = asyncio.Semaphore(settings.screener_concurrency)

        async def _bounded_fetch(code: str) -> StockRow | None:
            async with sem:
                return await _fetch_us_quote(code)

        fetched = await asyncio.gather(*(_bounded_fetch(c) for c in missing_us))
        us_quotes = dict(zip(missing_us, fetched, strict=True))
        return [
            snapshot.get(code) or us_quotes.get(code) or _placeholder_row(code)
            for code in codes
        ]
