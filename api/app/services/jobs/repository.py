from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite

from app.types.jobs import AgentStep, Job, JobStatus

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id       TEXT PRIMARY KEY,
    query        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    result       TEXT,
    error        TEXT,
    progress     TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    completed_at REAL
)
"""

_SELECT_COLUMNS = (
    "job_id, query, status, result, error, progress,"
    " created_at, updated_at, completed_at"
)

# done / error になった時点で completed_at を確定させる終端ステータス。
_TERMINAL_STATUSES = (JobStatus.DONE, JobStatus.ERROR)

# クラス内に list() メソッドがあるため、シグネチャでは組み込み list を直接書けない
_AgentSteps = list[AgentStep]


def _row_to_job(row: aiosqlite.Row) -> Job:
    progress_raw = row["progress"]
    progress = (
        [AgentStep.model_validate(s) for s in json.loads(str(progress_raw))]
        if progress_raw is not None
        else None
    )
    return Job(
        job_id=str(row["job_id"]),
        query=str(row["query"]),
        status=JobStatus(str(row["status"])),
        result=str(row["result"]) if row["result"] is not None else None,
        error=str(row["error"]) if row["error"] is not None else None,
        progress=progress,
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        completed_at=(
            float(row["completed_at"]) if row["completed_at"] is not None else None
        ),
    )


class JobRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        """テーブルを作成する。アプリ起動時に一度だけ呼ぶ。"""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            # 既存DB への追加カラムのマイグレーション
            async with db.execute("PRAGMA table_info(jobs)") as cursor:
                columns = {str(row[1]) for row in await cursor.fetchall()}
            if "progress" not in columns:
                await db.execute("ALTER TABLE jobs ADD COLUMN progress TEXT")
            if "completed_at" not in columns:
                await db.execute("ALTER TABLE jobs ADD COLUMN completed_at REAL")
            await db.commit()

    async def ping(self) -> bool:
        """DB接続が正常かを確認する。ヘルスチェック用。"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def create(self, job_id: str, query: str) -> Job:
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO jobs (job_id, query, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (job_id, query, JobStatus.PENDING, now, now),
            )
            await db.commit()
        return Job(
            job_id=job_id,
            query=query,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    async def get(self, job_id: str) -> Job | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM jobs WHERE job_id = ?",
                (job_id,),
            ) as cursor:
                row = await cursor.fetchone()
        return _row_to_job(row) if row is not None else None

    async def find_active(self, query: str) -> Job | None:
        """指定した query の未完了ジョブ（pending/running）のうち最新の1件を返す。

        スクリーナー自動更新（issue #73）の多重起動防止に使う。
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM jobs"
                " WHERE query = ? AND status IN (?, ?)"
                " ORDER BY created_at DESC LIMIT 1",
                (query, JobStatus.PENDING, JobStatus.RUNNING),
            ) as cursor:
                row = await cursor.fetchone()
        return _row_to_job(row) if row is not None else None

    async def create_if_not_active(self, job_id: str, query: str) -> Job | None:
        """同一 query の未完了ジョブ（pending/running）が無い場合に限り新規作成する。

        「未完了ジョブが無いか確認してから作る」を1つのSQL文（INSERT ... WHERE
        NOT EXISTS）で行うことで、check-then-act の間に別リクエストが割り込む
        レース（同時に複数タブから自動更新が発火した場合の多重起動）を防ぐ
        （issue #73）。作成できた場合のみ Job を返し、既に未完了ジョブが
        存在した場合は None を返す（呼び出し側は find_active() で既存の
        job_id を取得する）。
        """
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "INSERT INTO jobs (job_id, query, status, created_at, updated_at)"
                " SELECT ?, ?, ?, ?, ?"
                " WHERE NOT EXISTS ("
                "   SELECT 1 FROM jobs WHERE query = ? AND status IN (?, ?)"
                " )",
                (
                    job_id,
                    query,
                    JobStatus.PENDING,
                    now,
                    now,
                    query,
                    JobStatus.PENDING,
                    JobStatus.RUNNING,
                ),
            )
            await db.commit()
            created = cursor.rowcount == 1
        if not created:
            return None
        return Job(
            job_id=job_id,
            query=query,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    async def list(self, limit: int = 10) -> list[Job]:
        """最近のジョブ一覧を新しい順に返す。"""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT {_SELECT_COLUMNS} FROM jobs"
                " ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_job(row) for row in rows]

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        result: str | None = None,
        error: str | None = None,
    ) -> None:
        """ステータスを更新する。

        result/error は渡した場合のみ上書きする。done/error への遷移時は
        completed_at を確定させる。
        """
        now = time.time()
        completed_at = now if status in _TERMINAL_STATUSES else None
        async with aiosqlite.connect(self._db_path) as db:
            if result is not None or error is not None:
                await db.execute(
                    "UPDATE jobs SET status=?, result=?, error=?,"
                    " updated_at=?, completed_at=? WHERE job_id=?",
                    (status, result, error, now, completed_at, job_id),
                )
            else:
                await db.execute(
                    "UPDATE jobs SET status=?, updated_at=?, completed_at=?"
                    " WHERE job_id=?",
                    (status, now, completed_at, job_id),
                )
            await db.commit()

    async def update_progress(self, job_id: str, steps: _AgentSteps) -> None:
        """マルチエージェントの進捗（各ステップの状態・中間サマリー）を保存する。"""
        now = time.time()
        payload: list[dict[str, Any]] = [s.model_dump() for s in steps]
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE jobs SET progress=?, updated_at=? WHERE job_id=?",
                (json.dumps(payload, ensure_ascii=False), now, job_id),
            )
            await db.commit()
