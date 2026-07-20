"""ウォッチリストのユースケース: 登録コードとスナップショットの結合。

日本株はスクリーナーのスナップショットと結合する（従来通り）。米国株
（スクリーナー対象外）はスナップショットに存在しないため、共通の
quote_lookup（screener.us_quote）でquoteを解決する。
"""

from __future__ import annotations

from app.services.screener.repository import ScreenerRepository
from app.services.screener.us_quote import fetch_us_quotes, placeholder_row
from app.services.watchlist.repository import WatchlistRepository
from app.types.api import StockRow
from app.utils.market import is_jp_code


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
        us_quotes = await fetch_us_quotes(missing_us)
        return [
            snapshot.get(code) or us_quotes.get(code) or placeholder_row(code)
            for code in codes
        ]
