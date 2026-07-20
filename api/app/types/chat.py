"""チャット履歴（会話・メッセージ）の型定義。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Conversation(BaseModel):
    """会話（チャットのスレッド）。"""

    conversation_id: str
    title: str  # 初回メッセージから自動生成
    created_at: float
    updated_at: float


class Message(BaseModel):
    """会話内の 1 メッセージ。"""

    message_id: str
    conversation_id: str
    role: str  # "user" | "assistant"
    content: str
    created_at: float


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    # 銘柄選択→AI分析のように対象銘柄が既知の場合に明示指定する（任意）。
    # 指定時はエージェント側のテキストからの銘柄抽出（日本株コード限定）をスキップする。
    tickers: list[str] = Field(default_factory=list)


class SendMessageResponse(BaseModel):
    """送信受付結果（Job 非同期方式）。

    ユーザー発言は即時永続化し、AI 応答はエージェントジョブとして実行される。
    クライアントは job_id をポーリングし、完了時の回答は会話にも保存される。
    """

    conversation: Conversation
    user_message: Message
    job_id: str
