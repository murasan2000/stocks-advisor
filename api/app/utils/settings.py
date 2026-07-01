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
    # "mock": 決定論的な合成データを使用（既定・オフライン可）
    # "live": yfinance 実データ（到達不可時は合成へ自動フォールバック）
    external_api_mode: str = "live"
    mock_data_dir: str = "../data/mock"

    # スクリーナーの live 取得チューニング（yfinance レートリミット対策）
    # 株価は一括DL、ファンダは低並列＋バックオフ再試行で全銘柄を取り切る。
    screener_history_batch: int = 40  # yf.download 1回あたりの銘柄数
    screener_concurrency: int = 4  # ファンダメンタルズ取得の同時数
    screener_throttle_sec: float = 0.4  # バッチ間・リクエスト間の待機（秒）
    screener_max_retries: int = 5  # レートリミット時の最大再試行回数


settings = Settings()
