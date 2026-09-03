"""AI企業分析レポートの永続化（issue #72）。

銘柄コード×日付を主キーとして1件のレポートを保持する。同一銘柄・同一日付での
再実行（upsert）は既存行を上書きする。過去日の行は再実行経路が無いため実質
immutable。
"""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite

from app.types.api import CompanyReport

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS company_reports (
    code         TEXT NOT NULL,
    report_date  TEXT NOT NULL,
    content      TEXT NOT NULL,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    PRIMARY KEY (code, report_date)
)
"""

_SELECT_COLUMNS = "code, report_date, content, created_at, updated_at"


def _row_to_report(row: aiosqlite.Row) -> CompanyReport:
    return CompanyReport(
        code=str(row["code"]),
        report_date=str(row["report_date"]),
        content=str(row["content"]),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


class CompanyReportRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        """テーブルを作成する。アプリ起動時に一度だけ呼ぶ。"""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.commit()

    async def upsert(self, code: str, report_date: str, content: str) -> CompanyReport:
        """指定日のレポートを保存する（同一銘柄・同一日付は上書き）。

        呼び出し側に返す CompanyReport は書き込んだ値からその場で組み立てる
        （再SELECTしない。JobRepository.create() 等、既存repositoryと同じ方針）。
        そのため上書き時の created_at は本来の初回作成日時ではなく今回の
        書き込み時刻になるが、現状どの呼び出し元も created_at を参照しない
        （report_date が実質の識別子のため）ので許容する。
        """
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO company_reports"
                " (code, report_date, content, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (code, report_date) DO UPDATE SET"
                " content=excluded.content, updated_at=excluded.updated_at",
                (code, report_date, content, now, now),
            )
            await db.commit()
        return CompanyReport(
            code=code,
            report_date=report_date,
            content=content,
            created_at=now,
            updated_at=now,
        )

    async def get(self, code: str, report_date: str) -> CompanyReport | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM company_reports"
                " WHERE code = ? AND report_date = ?",
                (code, report_date),
            ) as cursor:
                row = await cursor.fetchone()
        return _row_to_report(row) if row is not None else None

    async def list_dates(self, code: str) -> list[str]:
        """レポートが存在する日付一覧を新しい順に返す（カレンダーの非活性判定用）。"""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT report_date FROM company_reports"
                " WHERE code = ? ORDER BY report_date DESC",
                (code,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [str(row[0]) for row in rows]
