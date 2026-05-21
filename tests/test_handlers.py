import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("ADMIN_GROUP_ID", "-100")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.bot import handlers
from app.db.models import Base, User


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_private_message_rejects_inactive_user(monkeypatch, db):
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(handlers, "send_message", fake_send_message)

    await handlers.handle_update(
        {"message": {"chat": {"id": 10, "type": "private"}, "from": {"id": 20}, "text": "Hi"}},
        db,
    )

    assert sent == [(10, handlers.UNAUTHORIZED_MESSAGE)]


@pytest.mark.asyncio
async def test_private_message_uses_no_context_fallback(monkeypatch, db):
    db.add(User(telegram_user_id=20, is_active=True))
    db.commit()
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(handlers, "send_message", fake_send_message)
    monkeypatch.setattr(handlers, "embed_texts", lambda texts: [[0.1, 0.2]])
    monkeypatch.setattr(handlers, "search_contexts", lambda *args, **kwargs: [])

    await handlers.handle_update(
        {"message": {"chat": {"id": 10, "type": "private"}, "from": {"id": 20}, "text": "Question"}},
        db,
    )

    assert sent == [(10, handlers.NO_CONTEXT_MESSAGE)]


@pytest.mark.asyncio
async def test_private_message_llm_error_is_reported_without_raising(monkeypatch, db):
    db.add(User(telegram_user_id=20, is_active=True))
    db.commit()
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    def broken_embed_texts(texts):
        raise RuntimeError("invalid api key")

    monkeypatch.setattr(handlers, "send_message", fake_send_message)
    monkeypatch.setattr(handlers, "embed_texts", broken_embed_texts)

    await handlers.handle_update(
        {"message": {"chat": {"id": 10, "type": "private"}, "from": {"id": 20}, "text": "Question"}},
        db,
    )

    assert sent == [(10, handlers.ERROR_MESSAGE)]
