from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from app.utils.settings import settings


class LLMProviderFactory:
    """
    ### LLM_PROVIDER 環境変数によって制御される
        - local   → LOCAL_LLM_BASE_URL を指す ChatOllama (Ollama)
        - bedrock → Amazon Bedrock 上の ChatBedrock (claude-sonnet etc.)

    ### インスタンスは get_llm() でキャッシュされ、アプリ全体で共有される。
    """

    @staticmethod
    def _secret_or_none(value: SecretStr) -> SecretStr | None:
        """空文字の SecretStr を None に変換する。"""
        return value if value.get_secret_value() else None

    @staticmethod
    @lru_cache(maxsize=1)
    def get_llm() -> BaseChatModel:
        """Amazon Bedrock またはローカル Ollama のいずれかの LLM インスタンスを返す。"""
        provider = settings.llm_provider

        if provider == "bedrock":
            from langchain_aws import ChatBedrock

            # 空文字は None にして、未指定時は AWS のデフォルト認証チェーンへ委譲する。
            key_id = LLMProviderFactory._secret_or_none(settings.aws_access_key_id)
            secret = LLMProviderFactory._secret_or_none(settings.aws_secret_access_key)
            token = LLMProviderFactory._secret_or_none(settings.aws_session_token)

            return ChatBedrock(
                model=settings.bedrock_model_id,
                region=settings.bedrock_region,
                aws_access_key_id=key_id,
                aws_secret_access_key=secret,
                aws_session_token=token,
                temperature=0.1,
            )

        if provider == "local":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=settings.local_llm_model,
                base_url=settings.local_llm_base_url,
                temperature=0.1,
            )

        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. Valid values: 'local', 'bedrock'."
        )
