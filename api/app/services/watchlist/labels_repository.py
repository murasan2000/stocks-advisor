"""ウォッチリスト銘柄へ付与するラベルの永続化（issue #68）。

ラベル本体（labels）と、銘柄コード×ラベルの多対多（watchlist_labels）を
既存の watchlist と同じ DB ファイルに保存する（テーブルのみ分ける。
ChatRepository の conversations/messages と同様、関連する複数テーブルを
1つのリポジトリでまとめて扱う）。

ラベルは並び順（ソートキー）ではなく絞り込み用のタグとして扱う方針のため、
複数ラベルを持つ銘柄の「代表ラベル」といった概念は持たない（issue #68 の
設計方針）。
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import aiosqlite

from app.types.api import Label

_CREATE_LABELS = """
CREATE TABLE IF NOT EXISTS labels (
    label_id   TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
)
"""

_CREATE_WATCHLIST_LABELS = """
CREATE TABLE IF NOT EXISTS watchlist_labels (
    code     TEXT NOT NULL,
    label_id TEXT NOT NULL,
    PRIMARY KEY (code, label_id)
)
"""

_CREATE_WATCHLIST_LABELS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_watchlist_labels_label
ON watchlist_labels (label_id)
"""


def _row_to_label(row: aiosqlite.Row) -> Label:
    return Label(
        label_id=str(row["label_id"]),
        name=str(row["name"]),
        created_at=float(row["created_at"]),
    )


class LabelsRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_LABELS)
            await db.execute(_CREATE_WATCHLIST_LABELS)
            await db.execute(_CREATE_WATCHLIST_LABELS_INDEX)
            await db.commit()

    # ------------------------------------------------------------------
    # ラベル本体
    # ------------------------------------------------------------------

    async def list_all(self) -> list[Label]:
        """全ラベルを名前順で返す（絞り込みチップ表示用）。"""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM labels ORDER BY name") as cursor:
                rows = await cursor.fetchall()
        return [_row_to_label(r) for r in rows]

    async def get_by_name(self, name: str) -> Label | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM labels WHERE name = ?", (name,)
            ) as cursor:
                row = await cursor.fetchone()
        return _row_to_label(row) if row is not None else None

    async def create(self, name: str) -> Label:
        """名前で新規作成する。同名が既にあればそれを返す（冪等）。

        「確認してから作成」の2ステップだが、name には UNIQUE 制約があるため、
        2つのタブ等からの同時作成で INSERT が競合した場合は例外を投げず、
        競合相手が作成した既存行を返す（自己レビューで指摘された同時作成レース）。
        """
        name = name.strip()
        existing = await self.get_by_name(name)
        if existing is not None:
            return existing
        label_id = str(uuid.uuid4())
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO labels (label_id, name, created_at) VALUES (?, ?, ?)",
                    (label_id, name, now),
                )
                await db.commit()
            except aiosqlite.IntegrityError:
                # 同時作成レース: UNIQUE制約違反時は競合相手が作成した既存行を返す
                raced = await self.get_by_name(name)
                if raced is not None:
                    return raced
                raise
        return Label(label_id=label_id, name=name, created_at=now)

    async def delete(self, label_id: str) -> None:
        """ラベル自体を削除する（存在しない銘柄への付与も含め連鎖して解除）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM labels WHERE label_id = ?", (label_id,))
            await db.execute(
                "DELETE FROM watchlist_labels WHERE label_id = ?", (label_id,)
            )
            await db.commit()

    # ------------------------------------------------------------------
    # 銘柄への付与
    # ------------------------------------------------------------------

    async def attach(self, code: str, label_id: str) -> None:
        """銘柄にラベルを付与する（冪等）。"""
        code = code.strip().upper()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO watchlist_labels (code, label_id)"
                " VALUES (?, ?)",
                (code, label_id),
            )
            await db.commit()

    async def detach(self, code: str, label_id: str) -> None:
        """銘柄からラベルを解除する（未付与でもエラーにしない）。"""
        code = code.strip().upper()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM watchlist_labels WHERE code = ? AND label_id = ?",
                (code, label_id),
            )
            await db.commit()

    async def labels_by_code(self, codes: list[str]) -> dict[str, list[Label]]:
        """指定コード群について、銘柄コード→付与ラベル一覧（名前順）のマップを返す。

        付与の無いコードはキー自体を含めない
        （呼び出し側は dict.get(code, []) 等で扱う）。
        """
        if not codes:
            return {}
        placeholders = ",".join("?" for _ in codes)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT wl.code AS code, l.label_id AS label_id, l.name AS name,"
                " l.created_at AS created_at"
                " FROM watchlist_labels wl JOIN labels l ON wl.label_id = l.label_id"
                f" WHERE wl.code IN ({placeholders})"
                " ORDER BY l.name",
                codes,
            ) as cursor:
                rows = await cursor.fetchall()
        result: dict[str, list[Label]] = {}
        for row in rows:
            result.setdefault(str(row["code"]), []).append(_row_to_label(row))
        return result
