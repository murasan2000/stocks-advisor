"""チャット送信 → エージェントジョブの実行と応答の永続化。

送信 API の入口を 1 本化する:
  1. ユーザー発言を会話に保存
  2. エージェントジョブ（親オーケストレーター）を作成
  3. ジョブ完了時に AI 応答を会話へ保存（クライアントは job_id をポーリング）
"""

from __future__ import annotations

import logging
import uuid

from app.services.agents.runner import run_agent_job
from app.services.chat.repository import ChatRepository
from app.services.jobs.repository import JobRepository
from app.types.chat import SendMessageResponse
from app.types.jobs import JobStatus

logger = logging.getLogger(__name__)


async def accept_message(
    chat_repo: ChatRepository,
    job_repo: JobRepository,
    conversation_id: str,
    content: str,
) -> SendMessageResponse | None:
    """ユーザー発言を保存し、応答生成ジョブを作成する（実行は呼び出し側で開始）。

    会話が存在しない場合は None。
    """
    conversation = await chat_repo.get_conversation(conversation_id)
    if conversation is None:
        return None

    user_message = await chat_repo.add_message(conversation_id, "user", content)
    job_id = str(uuid.uuid4())
    await job_repo.create(job_id, content)

    updated = await chat_repo.get_conversation(conversation_id)
    assert updated is not None
    return SendMessageResponse(
        conversation=updated, user_message=user_message, job_id=job_id
    )


async def run_chat_agent_job(
    job_id: str,
    job_repo: JobRepository,
    chat_repo: ChatRepository,
    conversation_id: str,
    query: str,
) -> None:
    """エージェントジョブを実行し、完了時に AI 応答を会話へ永続化する。"""
    await run_agent_job(job_id, job_repo, "auto", query)

    job = await job_repo.get(job_id)
    if job is None:  # 通常起こらないが、履歴保存は諦めてログのみ残す
        logger.error("chat agent job disappeared: %s", job_id)
        return
    if job.status == JobStatus.DONE and job.result:
        content = job.result
    else:
        content = f"回答の生成に失敗しました: {job.error or '不明なエラー'}"

    # 実行中に会話が削除された場合は保存しない（孤児メッセージを作らない）
    if await chat_repo.get_conversation(conversation_id) is None:
        logger.info(
            "conversation %s deleted during job %s; skip persisting reply",
            conversation_id,
            job_id,
        )
        return
    await chat_repo.add_message(conversation_id, "assistant", content)
