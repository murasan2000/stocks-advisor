"""ウォッチリストのユースケース: 登録コードとスナップショットの結合。"""

from __future__ import annotations

from app.services.external.symbols import to_yahoo_symbol
from app.services.screener.repository import ScreenerRepository
from app.services.watchlist.repository import WatchlistRepository
from app.types.api import StockRow


def _placeholder_row(code: str) -> StockRow:
    """スナップショットに存在しないコード（上場廃止等）向けの最小行。"""
    return StockRow(code=code, symbol=to_yahoo_symbol(code), name=code, market="")


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
        """登録順（新しい順）でスナップショット結合済みの行を返す。"""
        codes = await self._repo.list_codes()
        if not codes:
            return []
        snapshot = {r.code: r for r in await self._screener_repo.get_by_codes(codes)}
        return [snapshot.get(code) or _placeholder_row(code) for code in codes]
