"""ウォッチリスト（登録銘柄コード）の永続化（SQLite）。

銘柄の付随情報（名前・株価等）は保持しない。表示は ScreenerRepository の
スナップショットと code で結合して行う（スナップショットが正、の方針を踏襲）。
ジョブ・スクリーナーと同じ DB ファイルを共有し、テーブルのみ分ける。
"""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS watchlist (
    code TEXT PRIMARY KEY,
    added_at REAL NOT NULL
)
"""


class WatchlistRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.commit()

    async def add(self, code: str) -> None:
        """登録する（冪等。既に登録済みなら何もしない）。"""
        code = code.strip().upper()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO watchlist (code, added_at) VALUES (?, ?)",
                (code, time.time()),
            )
            await db.commit()

    async def remove(self, code: str) -> None:
        """解除する（未登録でもエラーにしない）。"""
        code = code.strip().upper()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM watchlist WHERE code = ?", (code,))
            await db.commit()

    async def list_codes(self) -> list[str]:
        """登録済みコードを追加日時の新しい順で返す。"""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT code FROM watchlist ORDER BY added_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [str(row[0]) for row in rows]
