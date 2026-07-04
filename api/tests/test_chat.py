"""チャット履歴（リポジトリ・送信サービス）のテスト。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.services.agents import general, runtime
from app.services.chat.repository import ChatRepository, make_title
from app.services.chat.service import accept_message, run_chat_agent_job
from app.services.jobs.repository import JobRepository
from app.types.jobs import JobStatus


@pytest.fixture
async def repo(tmp_path: Path) -> ChatRepository:
    r = ChatRepository(str(tmp_path / "chat.db"))
    await r.initialize()
    return r


@pytest.fixture
async def job_repo(tmp_path: Path) -> JobRepository:
    r = JobRepository(str(tmp_path / "jobs.db"))
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


async def test_accept_message_persists_user_and_creates_job(
    repo: ChatRepository, job_repo: JobRepository
) -> None:
    conv = await repo.create_conversation()
    result = await accept_message(repo, job_repo, conv.conversation_id, "こんにちは")
    assert result is not None
    assert result.user_message.role == "user"
    assert result.conversation.title == "こんにちは"

    job = await job_repo.get(result.job_id)
    assert job is not None and job.status == JobStatus.PENDING

    # 存在しない会話は None
    assert await accept_message(repo, job_repo, "missing", "x") is None


async def test_run_chat_agent_job_persists_assistant(
    repo: ChatRepository,
    job_repo: JobRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_llm(
        system: str, user: str, *, fallback: str, config: Any = None
    ) -> str:
        return f"[LLM] {user}"

    async def _fake_intent(
        system: str, user: str, *, fallback: str, config: Any = None
    ) -> str:
        return fallback

    monkeypatch.setattr(general, "invoke_llm", _fake_llm)
    # 意図判定のオフライン・リトライ実時間待ちを避ける
    monkeypatch.setattr(runtime, "invoke_llm", _fake_intent)

    conv = await repo.create_conversation()
    accepted = await accept_message(
        repo, job_repo, conv.conversation_id, "PERとは何ですか"
    )
    assert accepted is not None

    await run_chat_agent_job(
        accepted.job_id, job_repo, repo, conv.conversation_id, "PERとは何ですか"
    )

    # ジョブ完了 + assistant メッセージが会話へ永続化される
    job = await job_repo.get(accepted.job_id)
    assert job is not None and job.status == JobStatus.DONE
    messages = await repo.list_messages(conv.conversation_id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[-1].content == "[LLM] PERとは何ですか"
