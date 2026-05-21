from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_webhook_secret: str = ""
    admin_group_id: int

    database_url: str
    redis_url: str
    qdrant_url: str
    qdrant_collection: str = "documents"

    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4.1-mini"

    retrieval_limit: int = 5
    retrieval_score_threshold: float = 0.35
    chunk_size: int = 1200
    chunk_overlap: int = 180

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
