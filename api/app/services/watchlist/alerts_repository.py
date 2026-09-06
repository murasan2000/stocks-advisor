"""ウォッチ銘柄の価格・スコア変化アラートの永続化（issue #81・候補A: アプリ内通知）。

候補A（アプリ内通知）採用のため Web Push・メール送信は行わず、検出結果を
SQLiteへ保存し、次回アクセス時にAPI経由で一覧表示する。既存の watchlist と
同じDBファイルを共有し、テーブルのみ分ける（他 watchlist 系 repository と同じ方針）。
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Literal, cast

import aiosqlite

from app.services.watchlist.alerts import DetectedAlert
from app.types.api import WatchlistAlert

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS watchlist_alerts (
    alert_id   TEXT PRIMARY KEY,
    code       TEXT NOT NULL,
    kind       TEXT NOT NULL,
    old_value  REAL NOT NULL,
    new_value  REAL NOT NULL,
    change_pct REAL,
    created_at REAL NOT NULL,
    read       INTEGER NOT NULL DEFAULT 0
)
"""

_SELECT_COLUMNS = (
    "alert_id, code, kind, old_value, new_value, change_pct, created_at, read"
)


def _row_to_alert(row: aiosqlite.Row) -> WatchlistAlert:
    return WatchlistAlert(
        alert_id=str(row["alert_id"]),
        code=str(row["code"]),
        kind=cast(Literal["price", "score"], str(row["kind"])),
        old_value=float(row["old_value"]),
        new_value=float(row["new_value"]),
        change_pct=(
            float(row["change_pct"]) if row["change_pct"] is not None else None
        ),
        created_at=float(row["created_at"]),
        read=bool(row["read"]),
    )


class AlertsRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        """テーブルを作成する。アプリ起動時に一度だけ呼ぶ。"""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.commit()

    async def create_many(self, alerts: list[DetectedAlert]) -> None:
        """検出結果（DetectedAlert）をまとめて保存する。

        alert_id・created_at はここで採番する（detect_alerts() は純粋関数のため
        時刻・IDを持たない）。
        """
        if not alerts:
            return
        now = time.time()
        values = [
            (
                str(uuid.uuid4()),
                a.code,
                a.kind,
                a.old_value,
                a.new_value,
                a.change_pct,
                now,
                0,
            )
            for a in alerts
        ]
        async with aiosqlite.connect(self._db_path) as db:
            await db.executemany(
                "INSERT INTO watchlist_alerts"
                " (alert_id, code, kind, old_value, new_value, change_pct,"
                " created_at, read) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )
            await db.commit()

    async def list_unread(self) -> list[WatchlistAlert]:
        """未読アラートを新しい順で返す。"""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM watchlist_alerts"
                " WHERE read = 0 ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_alert(r) for r in rows]

    async def list_all(self, limit: int = 50) -> list[WatchlistAlert]:
        """既読・未読を問わず新しい順で返す（履歴表示用）。"""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM watchlist_alerts"
                " ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_alert(r) for r in rows]

    async def mark_all_read(self) -> None:
        """全件を既読にする。"""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("UPDATE watchlist_alerts SET read = 1 WHERE read = 0")
            await db.commit()
