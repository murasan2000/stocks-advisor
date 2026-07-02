"""チャット応答の生成。

現状はモック応答（Phase 4/5 で親エージェント＝Job 実行に差し替える）。
フロントではなくサーバ側で生成することで、履歴の永続化と将来のエージェント
接続を同じ入口（メッセージ送信 API）に集約する。
"""

from __future__ import annotations

from app.services.chat.repository import ChatRepository
from app.types.chat import SendMessageResponse


def generate_reply(content: str) -> str:
    """暫定のモック応答を返す。

    TODO(Phase 4/5): 親エージェント（LangGraph）への委任・Job 実行に差し替える。
    """
    return (
        "AIエージェントは現在準備中です（Phase 4 以降で接続予定）。\n\n"
        f"ご質問「{content}」には、企業分析・一般質問エージェントの実装後に"
        "お答えします。"
    )


async def send_message(
    repo: ChatRepository, conversation_id: str, content: str
) -> SendMessageResponse | None:
    """ユーザー発言を保存し、応答を生成・保存して返す。

    会話が存在しない場合は None。
    """
    conversation = await repo.get_conversation(conversation_id)
    if conversation is None:
        return None

    user_message = await repo.add_message(conversation_id, "user", content)
    assistant_message = await repo.add_message(
        conversation_id, "assistant", generate_reply(content)
    )
    updated = await repo.get_conversation(conversation_id)
    assert updated is not None
    return SendMessageResponse(
        conversation=updated,
        user_message=user_message,
        assistant_message=assistant_message,
    )
