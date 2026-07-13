"""保有銘柄のユースケース: 登録・削除・CSVインポート・スナップショット結合。"""

from __future__ import annotations

from app.services.external.symbols import to_yahoo_symbol
from app.services.portfolio.csv_import import (
    decode_csv_bytes,
    merge_duplicate_codes,
    parse_rakuten_holdings_csv,
)
from app.services.portfolio.repository import HoldingsRepository
from app.services.screener.repository import ScreenerRepository
from app.types.api import Holding, ImportResult, StockRow


def _to_holding(
    code: str, quantity: float, avg_cost: float, snap: StockRow | None
) -> Holding:
    cost_value = quantity * avg_cost
    price = snap.price if snap else None
    market_value = quantity * price if price is not None else None
    pnl = market_value - cost_value if market_value is not None else None
    pnl_pct = (pnl / cost_value * 100) if pnl is not None and cost_value else None
    return Holding(
        code=code,
        symbol=snap.symbol if snap else to_yahoo_symbol(code),
        name=snap.name if snap else code,
        market=snap.market if snap else "",
        quantity=quantity,
        avg_cost=avg_cost,
        price=price,
        cost_value=cost_value,
        market_value=market_value,
        pnl=pnl,
        pnl_pct=pnl_pct,
    )


class PortfolioService:
    def __init__(
        self, repo: HoldingsRepository, screener_repo: ScreenerRepository
    ) -> None:
        self._repo = repo
        self._screener_repo = screener_repo

    async def upsert(self, code: str, quantity: float, avg_cost: float) -> None:
        await self._repo.upsert(code, quantity, avg_cost)

    async def remove(self, code: str) -> None:
        await self._repo.remove(code)

    async def import_csv(self, data: bytes) -> ImportResult:
        """CSVをパースしてアップサートする（CSVに無い既存銘柄は削除しない）。"""
        text = decode_csv_bytes(data)
        parsed = merge_duplicate_codes(parse_rakuten_holdings_csv(text))
        if parsed:
            await self._repo.upsert_many(
                [(h.code, h.quantity, h.avg_cost) for h in parsed]
            )
        return ImportResult(imported=len(parsed))

    async def list_holdings(self) -> list[Holding]:
        rows = await self._repo.list_all()
        if not rows:
            return []
        codes = [code for code, _, _ in rows]
        snapshot = {r.code: r for r in await self._screener_repo.get_by_codes(codes)}
        return [
            _to_holding(code, quantity, avg_cost, snapshot.get(code))
            for code, quantity, avg_cost in rows
        ]
