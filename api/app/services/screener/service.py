"""スクリーナーのユースケース: スナップショット更新と絞り込みクエリ。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.services.screener.fetcher import fetch_row
from app.services.screener.metrics import is_oversold_rebound
from app.services.screener.repository import ScreenerRepository
from app.services.screener.universe import (
    Ticker,
    fetch_jpx_universe,
    load_universe,
    save_universe,
    universe_source,
)
from app.types.api import ScreenerMeta, ScreenerSummary, StockRow, StocksResponse
from app.utils.settings import settings

logger = logging.getLogger(__name__)

PAGE_SIZE = 100  # 段階取得 1 ステージあたりの件数
_REFRESH_CONCURRENCY = 12  # yfinance 同時取得数

_SORT_KEYS = frozenset(
    {
        "score",
        "per",
        "pbr",
        "dividend_yield",
        "roe",
        "market_cap",
        "change_pct",
        "rsi",
        "code",
    }
)


@dataclass
class ScreenerFilters:
    """絞り込み条件。None の項目は無効（条件として使わない）。"""

    markets: list[str] = field(default_factory=list)
    per_min: float | None = None
    per_max: float | None = None
    pbr_max: float | None = None
    dividend_yield_min: float | None = None
    roe_min: float | None = None
    market_cap_min: float | None = None  # 円
    market_cap_max: float | None = None
    rsi_min: float | None = None
    rsi_max: float | None = None
    # 下がりすぎ反発検出
    oversold_enabled: bool = False
    drop_from_high_pct: float = 50.0
    rebound_from_low_pct: float = 10.0
    # 表示
    query: str | None = None  # コード・銘柄名の部分一致
    sort_by: str = "score"
    sort_desc: bool = True


def _passes(row: StockRow, f: ScreenerFilters) -> bool:
    if f.markets and row.market not in f.markets:
        return False
    if f.query:
        q = f.query.strip().lower()
        if q not in row.code.lower() and q not in row.name.lower():
            return False
    if f.per_min is not None and (row.per is None or row.per < f.per_min):
        return False
    if f.per_max is not None and (row.per is None or row.per > f.per_max):
        return False
    if f.pbr_max is not None and (row.pbr is None or row.pbr > f.pbr_max):
        return False
    if f.dividend_yield_min is not None and (
        row.dividend_yield is None or row.dividend_yield < f.dividend_yield_min
    ):
        return False
    if f.roe_min is not None and (row.roe is None or row.roe < f.roe_min):
        return False
    if f.market_cap_min is not None and (
        row.market_cap is None or row.market_cap < f.market_cap_min
    ):
        return False
    if f.market_cap_max is not None and (
        row.market_cap is None or row.market_cap > f.market_cap_max
    ):
        return False
    if f.rsi_min is not None and (row.rsi is None or row.rsi < f.rsi_min):
        return False
    if f.rsi_max is not None and (row.rsi is None or row.rsi > f.rsi_max):
        return False
    if f.oversold_enabled and not is_oversold_rebound(
        row.drop_from_high_pct,
        row.rebound_from_low_pct,
        min_drop=f.drop_from_high_pct,
        min_rebound=f.rebound_from_low_pct,
    ):
        return False
    return True


def _sort_key(sort_by: str) -> Callable[[StockRow], tuple[int, float]]:
    key = sort_by if sort_by in _SORT_KEYS else "score"

    def getter(row: StockRow) -> tuple[int, float]:
        value = getattr(row, key)
        if key == "code":
            # コードは数値化できないため別扱い（文字列順は score 昇順比較で代替不可）
            value = float(int("".join(ch for ch in row.code if ch.isdigit()) or 0))
        # None は常に末尾へ（is_none フラグを第1キーに）
        return (1, 0.0) if value is None else (0, float(value))

    return getter


def _summary(rows: list[StockRow]) -> ScreenerSummary:
    def _avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    pers = [r.per for r in rows if r.per is not None]
    divs = [r.dividend_yield for r in rows if r.dividend_yield is not None]
    roes = [r.roe for r in rows if r.roe is not None]
    up = sum(1 for r in rows if r.change_pct is not None and r.change_pct > 0)
    down = sum(1 for r in rows if r.change_pct is not None and r.change_pct < 0)
    unchanged = sum(1 for r in rows if r.change_pct is not None and r.change_pct == 0)
    return ScreenerSummary(
        count=len(rows),
        avg_per=_avg(pers),
        avg_dividend_yield=_avg(divs),
        avg_roe=_avg(roes),
        up=up,
        down=down,
        unchanged=unchanged,
    )


class ScreenerService:
    def __init__(self, repo: ScreenerRepository) -> None:
        self._repo = repo

    async def _resolve_universe(self) -> list[Ticker]:
        """更新対象のユニバースを決める。

        live では JPX から全銘柄を取得してディスクへキャッシュする。失敗時は
        キャッシュ/同梱シードにフォールバックする。mock はシードを使う。
        """
        if settings.external_api_mode != "live":
            return load_universe()
        try:
            universe = await asyncio.to_thread(fetch_jpx_universe)
            save_universe(universe, source="jpx")
            logger.info("fetched JPX universe: %d tickers", len(universe))
            return universe
        except Exception as exc:
            logger.warning("JPX universe fetch failed, fallback: %s", exc)
            return load_universe()

    async def refresh(
        self,
        progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> int:
        """ユニバース全銘柄を取得してスナップショットを置き換える。

        Args:
            progress: (done, total) を受け取る進捗コールバック（任意）。
        Returns:
            キャッシュした銘柄数（取得できなかった銘柄は除外）。
        """
        universe = await self._resolve_universe()
        total = len(universe)
        sem = asyncio.Semaphore(_REFRESH_CONCURRENCY)
        done = 0

        async def _one(idx: int) -> StockRow | None:
            nonlocal done
            async with sem:
                row = await fetch_row(universe[idx])
            done += 1
            if progress and (done % 25 == 0 or done == total):
                await progress(done, total)
            return row

        results = await asyncio.gather(*(_one(i) for i in range(total)))
        rows = [r for r in results if r is not None]
        await self._repo.replace_all(
            rows, source=settings.external_api_mode, universe_count=total
        )
        logger.info(
            "screener snapshot refreshed: %d/%d stocks (skipped %d)",
            len(rows),
            total,
            total - len(rows),
        )
        return len(rows)

    async def query(self, filters: ScreenerFilters, stage: int) -> StocksResponse:
        """フィルタを適用し、指定ステージ分のページを返す。"""
        all_rows = await self._repo.get_all()
        filtered = [r for r in all_rows if _passes(r, filters)]
        filtered.sort(key=_sort_key(filters.sort_by), reverse=filters.sort_desc)

        stage = max(1, stage)
        start = (stage - 1) * PAGE_SIZE
        page = filtered[start : start + PAGE_SIZE]
        next_stage = stage + 1 if start + PAGE_SIZE < len(filtered) else None

        last_refresh, source, universe_count = await self._repo.get_meta()
        meta = ScreenerMeta(
            last_refresh=last_refresh,
            universe_count=universe_count or len(load_universe()),
            snapshot_count=len(all_rows),
            source=source or universe_source(),
        )
        return StocksResponse(
            stocks=page,
            stage=stage,
            next_stage=next_stage,
            total=len(filtered),
            summary=_summary(filtered),
            meta=meta,
        )
