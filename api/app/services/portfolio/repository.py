"""保有銘柄（数量・平均取得単価）の永続化（SQLite）。

銘柄の付随情報（名前・株価等）は保持しない。表示は ScreenerRepository の
スナップショットと code で結合して行う（ウォッチリストと同じ方針）。
ジョブ・スクリーナー・ウォッチリストと同じ DB ファイルを共有し、テーブルのみ分ける。
"""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS holdings (
    code TEXT PRIMARY KEY,
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    updated_at REAL NOT NULL
)
"""


class HoldingsRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.commit()

    async def upsert(self, code: str, quantity: float, avg_cost: float) -> None:
        """追加/更新する（既存なら数量・平均取得単価を上書き）。"""
        code = code.strip().upper()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO holdings (code, quantity, avg_cost, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(code) DO UPDATE SET"
                " quantity=excluded.quantity, avg_cost=excluded.avg_cost,"
                " updated_at=excluded.updated_at",
                (code, quantity, avg_cost, time.time()),
            )
            await db.commit()

    async def upsert_many(self, holdings: list[tuple[str, float, float]]) -> None:
        """複数銘柄をまとめてアップサートする（CSVインポート用）。"""
        now = time.time()
        rows = [(c.strip().upper(), q, a, now) for c, q, a in holdings]
        async with aiosqlite.connect(self._db_path) as db:
            await db.executemany(
                "INSERT INTO holdings (code, quantity, avg_cost, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(code) DO UPDATE SET"
                " quantity=excluded.quantity, avg_cost=excluded.avg_cost,"
                " updated_at=excluded.updated_at",
                rows,
            )
            await db.commit()

    async def remove(self, code: str) -> None:
        """削除する（未登録でもエラーにしない）。"""
        code = code.strip().upper()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM holdings WHERE code = ?", (code,))
            await db.commit()

    async def list_all(self) -> list[tuple[str, float, float]]:
        """(code, quantity, avg_cost) を code 順で返す。"""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT code, quantity, avg_cost FROM holdings ORDER BY code"
            ) as cursor:
                rows = await cursor.fetchall()
        return [(str(r[0]), float(r[1]), float(r[2])) for r in rows]
