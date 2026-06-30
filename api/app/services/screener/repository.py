"""スクリーニング用スナップショットキャッシュ（SQLite）。

全銘柄を一気に yfinance 取得すると数分かかるため、定期的に取得した結果を
キャッシュし、API はキャッシュから高速に返す。ジョブ DB と同じ SQLite ファイルを
共有し、テーブルを分けて持つ。
"""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite

from app.types.api import StockRow

_CREATE_SNAPSHOT = """
CREATE TABLE IF NOT EXISTS stocks_snapshot (
    code TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    market TEXT NOT NULL,
    price REAL, change_pct REAL, volume INTEGER, market_cap REAL,
    per REAL, pbr REAL, dividend_yield REAL, roe REAL, rsi REAL,
    high_5y REAL, low_1y REAL, drop_from_high_pct REAL, rebound_from_low_pct REAL,
    score INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_META = """
CREATE TABLE IF NOT EXISTS screener_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_refresh REAL,
    source TEXT,
    universe_count INTEGER
)
"""

_COLUMNS = (
    "code, symbol, name, market, price, change_pct, volume, market_cap, "
    "per, pbr, dividend_yield, roe, rsi, high_5y, low_1y, "
    "drop_from_high_pct, rebound_from_low_pct, score"
)
_FIELDS = _COLUMNS.replace(" ", "").split(",")


class ScreenerRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_SNAPSHOT)
            await db.execute(_CREATE_META)
            # 既存DB（universe_count カラムなし）へのマイグレーション
            async with db.execute("PRAGMA table_info(screener_meta)") as cursor:
                cols = {str(row[1]) for row in await cursor.fetchall()}
            if "universe_count" not in cols:
                await db.execute(
                    "ALTER TABLE screener_meta ADD COLUMN universe_count INTEGER"
                )
            await db.commit()

    async def replace_all(
        self, rows: list[StockRow], source: str, universe_count: int
    ) -> None:
        """スナップショットを丸ごと置き換え、最終更新メタを更新する。"""
        placeholders = ", ".join(["?"] * len(_FIELDS))
        values = [tuple(getattr(r, f) for f in _FIELDS) for r in rows]
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM stocks_snapshot")
            await db.executemany(
                f"INSERT INTO stocks_snapshot ({_COLUMNS}) VALUES ({placeholders})",
                values,
            )
            await db.execute(
                "INSERT INTO screener_meta (id, last_refresh, source, universe_count)"
                " VALUES (1, ?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET last_refresh=excluded.last_refresh,"
                " source=excluded.source, universe_count=excluded.universe_count",
                (time.time(), source, universe_count),
            )
            await db.commit()

    async def get_all(self) -> list[StockRow]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT {_COLUMNS} FROM stocks_snapshot"
            ) as cursor:
                rows = await cursor.fetchall()
        return [StockRow(**dict(row)) for row in rows]

    async def count(self) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM stocks_snapshot") as cursor:
                row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def get_meta(self) -> tuple[float | None, str | None, int]:
        """(last_refresh, source, universe_count) を返す。"""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT last_refresh, source, universe_count"
                " FROM screener_meta WHERE id = 1"
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None, None, 0
        return (
            float(row[0]) if row[0] is not None else None,
            str(row[1]) if row[1] is not None else None,
            int(row[2]) if row[2] is not None else 0,
        )
