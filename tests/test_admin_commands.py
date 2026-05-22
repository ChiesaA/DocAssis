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

from app.admin.commands import HELP_TEXT, parse_admin_command
from app.bot import handlers
from app.db.models import Base


def test_parse_help_command():
    assert parse_admin_command("/help") == ("help", [])


def test_parse_status_command():
    assert parse_admin_command("/status") == ("status", [])


def test_parse_retry_command_with_document_id():
    assert parse_admin_command("/retry 12") == ("retry", ["12"])


def test_parse_non_command_returns_none():
    assert parse_admin_command("hello") is None


@pytest.mark.asyncio
async def test_admin_help_command_sends_help(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin_group_id = handlers.get_settings().admin_group_id
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(handlers, "send_message", fake_send_message)

    await handlers.handle_update(
        {"message": {"chat": {"id": admin_group_id, "type": "group"}, "text": "/help"}},
        db,
    )

    assert sent == [(admin_group_id, HELP_TEXT)]
