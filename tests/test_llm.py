import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("ADMIN_GROUP_ID", "-100")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test")

from app.config import Settings
from app.rag.llm import (
    build_gemini_batch_embeddings_request,
    build_openai_client,
    normalize_gemini_model_name,
    uses_gemini_api,
)


def test_settings_accepts_openai_base_url():
    settings = Settings(
        telegram_bot_token="token",
        admin_group_id=-100,
        database_url="sqlite+pysqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        openai_api_key="gemini-key",
        openai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    assert settings.openai_base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_build_openai_client_uses_configured_base_url():
    settings = Settings(
        telegram_bot_token="token",
        admin_group_id=-100,
        database_url="sqlite+pysqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        openai_api_key="gemini-key",
        openai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    client = build_openai_client(settings)

    assert str(client.base_url) == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_gemini_api_is_detected_from_base_url():
    settings = Settings(
        telegram_bot_token="token",
        admin_group_id=-100,
        database_url="sqlite+pysqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        openai_api_key="gemini-key",
        openai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    assert uses_gemini_api(settings) is True


def test_gemini_embedding_request_uses_native_batch_endpoint():
    url, body = build_gemini_batch_embeddings_request(["alpha", "beta"], "gemini/gemini-embedding-001")

    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
    assert body == {
        "requests": [
            {"model": "models/gemini-embedding-001", "content": {"parts": [{"text": "alpha"}]}},
            {"model": "models/gemini-embedding-001", "content": {"parts": [{"text": "beta"}]}},
        ]
    }


def test_normalize_gemini_model_name_removes_router_prefix():
    assert normalize_gemini_model_name("gemini/gemini-embedding-001") == "gemini-embedding-001"
    assert normalize_gemini_model_name("gemini-embedding-001") == "gemini-embedding-001"
