"""チャット履歴（リポジトリ・送信サービス）のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.chat.repository import ChatRepository, make_title
from app.services.chat.service import send_message


@pytest.fixture
async def repo(tmp_path: Path) -> ChatRepository:
    r = ChatRepository(str(tmp_path / "chat.db"))
    await r.initialize()
    return r


def test_make_title_truncates_and_flattens() -> None:
    assert make_title("PERとは？") == "PERとは？"
    assert make_title("改行\nを  含む   質問") == "改行 を 含む 質問"
    long = "あ" * 50
    title = make_title(long)
    assert len(title) == 30
    assert title.endswith("…")


async def test_conversation_lifecycle(repo: ChatRepository) -> None:
    conv = await repo.create_conversation()
    assert conv.title == ""

    # 初回メッセージでタイトルが自動設定される
    await repo.add_message(conv.conversation_id, "user", "トヨタの株価は？")
    updated = await repo.get_conversation(conv.conversation_id)
    assert updated is not None
    assert updated.title == "トヨタの株価は？"
    assert updated.updated_at >= conv.updated_at

    # 2通目ではタイトルは変わらない
    await repo.add_message(conv.conversation_id, "assistant", "回答テキスト")
    again = await repo.get_conversation(conv.conversation_id)
    assert again is not None and again.title == "トヨタの株価は？"

    messages = await repo.list_messages(conv.conversation_id)
    assert [m.role for m in messages] == ["user", "assistant"]


async def test_list_and_search_conversations(repo: ChatRepository) -> None:
    a = await repo.create_conversation()
    await repo.add_message(a.conversation_id, "user", "PERとは何ですか")
    b = await repo.create_conversation()
    await repo.add_message(b.conversation_id, "user", "トヨタを分析して")

    listed = await repo.list_conversations()
    # 更新日時の新しい順（b が後に更新された）
    assert [c.conversation_id for c in listed] == [
        b.conversation_id,
        a.conversation_id,
    ]

    found = await repo.list_conversations(query="PER")
    assert [c.conversation_id for c in found] == [a.conversation_id]


async def test_delete_conversation_cascades(repo: ChatRepository) -> None:
    conv = await repo.create_conversation()
    await repo.add_message(conv.conversation_id, "user", "削除テスト")

    assert await repo.delete_conversation(conv.conversation_id) is True
    assert await repo.get_conversation(conv.conversation_id) is None
    assert await repo.list_messages(conv.conversation_id) == []
    # 二重削除は False
    assert await repo.delete_conversation(conv.conversation_id) is False


async def test_send_message_persists_pair(repo: ChatRepository) -> None:
    conv = await repo.create_conversation()
    result = await send_message(repo, conv.conversation_id, "こんにちは")
    assert result is not None
    assert result.user_message.role == "user"
    assert result.assistant_message.role == "assistant"
    assert result.conversation.title == "こんにちは"

    messages = await repo.list_messages(conv.conversation_id)
    assert len(messages) == 2

    # 存在しない会話は None
    assert await send_message(repo, "missing", "x") is None
