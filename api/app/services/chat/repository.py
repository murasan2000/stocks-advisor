"""チャット履歴リポジトリ（SQLite）。

会話（conversations）とメッセージ（messages）を既存のジョブ DB と同じ
SQLite ファイルに保存する（settings.db_path を共有、テーブルを分ける）。
"""

from __future__ import annotations

import time
import uuid

import aiosqlite

from app.types.chat import Conversation, Message

_CREATE_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    title           TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
)
"""

_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      REAL NOT NULL
)
"""

_CREATE_MESSAGES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_conversation
ON messages (conversation_id, created_at)
"""

_TITLE_MAX_LEN = 30


def make_title(content: str) -> str:
    """初回メッセージから会話タイトルを生成する（先頭を切り出し）。"""
    title = " ".join(content.split())  # 改行・連続空白を畳む
    if len(title) <= _TITLE_MAX_LEN:
        return title
    return title[: _TITLE_MAX_LEN - 1] + "…"


def _row_to_conversation(row: aiosqlite.Row) -> Conversation:
    return Conversation(
        conversation_id=str(row["conversation_id"]),
        title=str(row["title"]),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def _row_to_message(row: aiosqlite.Row) -> Message:
    return Message(
        message_id=str(row["message_id"]),
        conversation_id=str(row["conversation_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        created_at=float(row["created_at"]),
    )


class ChatRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_CONVERSATIONS)
            await db.execute(_CREATE_MESSAGES)
            await db.execute(_CREATE_MESSAGES_INDEX)
            await db.commit()

    # ------------------------------------------------------------------
    # 会話
    # ------------------------------------------------------------------

    async def create_conversation(self) -> Conversation:
        now = time.time()
        conversation_id = str(uuid.uuid4())
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO conversations"
                " (conversation_id, title, created_at, updated_at)"
                " VALUES (?, '', ?, ?)",
                (conversation_id, now, now),
            )
            await db.commit()
        return Conversation(
            conversation_id=conversation_id, title="", created_at=now, updated_at=now
        )

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ) as cursor:
                row = await cursor.fetchone()
        return _row_to_conversation(row) if row else None

    async def list_conversations(
        self, limit: int = 30, query: str | None = None
    ) -> list[Conversation]:
        """会話一覧を更新日時の新しい順で返す。query 指定でタイトル部分一致検索。"""
        sql = "SELECT * FROM conversations"
        params: list[object] = []
        if query and query.strip():
            sql += " WHERE title LIKE ?"
            params.append(f"%{query.strip()}%")
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_conversation(r) for r in rows]

    async def delete_conversation(self, conversation_id: str) -> bool:
        """会話と配下のメッセージを削除する。存在しなければ False。"""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
            await db.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # メッセージ
    # ------------------------------------------------------------------

    async def add_message(
        self, conversation_id: str, role: str, content: str
    ) -> Message:
        """メッセージを保存する。

        会話の updated_at を更新し、タイトル未設定なら本文から自動生成する。
        """
        now = time.time()
        message_id = str(uuid.uuid4())
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO messages"
                " (message_id, conversation_id, role, content, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (message_id, conversation_id, role, content, now),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = ?,"
                " title = CASE WHEN title = '' THEN ? ELSE title END"
                " WHERE conversation_id = ?",
                (now, make_title(content), conversation_id),
            )
            await db.commit()
        return Message(
            message_id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=now,
        )

    async def list_messages(self, conversation_id: str) -> list[Message]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM messages WHERE conversation_id = ?"
                " ORDER BY created_at, message_id",
                (conversation_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_message(r) for r in rows]
