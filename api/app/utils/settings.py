from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Cloud Provider
    # Supported values: "aws" or "azure"
    cloud_provider: str = "aws"
    aws_access_key_id: SecretStr = SecretStr("")
    aws_secret_access_key: SecretStr = SecretStr("")
    aws_session_token: SecretStr = SecretStr("")  # for temporary STS credentials

    # LLM Provider
    # Supported values: "bedrock" or "local"
    llm_provider: str = "local"
    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-6"
    bedrock_region: str = "ap-northeast-1"
    local_llm_base_url: str = "http://host.docker.internal:11434"
    local_llm_model: str = "gpt-oss:20b"

    # Langfuse
    langfuse_host: str = "http://host.docker.internal:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # Database
    # db/ はリポジトリ直下の独立コンポーネント（将来 Aurora 等の DB サービスに置換予定）。
    # 開発時は api/ から起動するため "../db/" を参照する。
    # コンテナでは DB_PATH=/app/db/stock_advisor.db を環境変数で上書きする。
    db_path: str = "../db/stock_advisor.db"

    # External API
    # "mock": data/mock/ のモックデータ・決定論的合成を使用
    # "live": 実データ（Market Agent は yfinance。到達不可時は合成へ自動フォールバック）
    # data/ はリポジトリ直下の独立コンポーネント（将来 S3 等のストレージに置換予定）。
    external_api_mode: str = "mock"
    mock_data_dir: str = "../data/mock"


settings = Settings()
