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

from app.admin.commands import HELP_TEXT, build_retry_response, format_status_message, parse_admin_command
from app.bot import handlers
from app.db.models import Base, Document


def test_parse_help_command():
    assert parse_admin_command("/help") == ("help", [])


def test_parse_status_command():
    assert parse_admin_command("/status") == ("status", [])


def test_parse_retry_command_with_document_id():
    assert parse_admin_command("/retry 12") == ("retry", ["12"])


def test_parse_non_command_returns_none():
    assert parse_admin_command("hello") is None


def test_format_status_message_lists_recent_documents():
    documents = [
        Document(id=2, file_name="b.txt", status="indexed"),
        Document(id=1, file_name="a.txt", status="failed", error_message="boom"),
    ]

    assert format_status_message(documents) == (
        "5 file gần nhất:\n"
        "#2 b.txt - indexed\n"
        "#1 a.txt - failed - boom"
    )


def test_format_status_message_handles_empty_list():
    assert format_status_message([]) == "Chưa có file nào."


def test_build_retry_response_requires_numeric_id():
    assert build_retry_response([]) == (None, "Dùng: /retry <document_id>")
    assert build_retry_response(["abc"]) == (None, "document_id phải là số.")


def test_build_retry_response_accepts_numeric_id():
    assert build_retry_response(["42"]) == (42, "")


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


@pytest.mark.asyncio
async def test_admin_status_command_sends_recent_documents(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin_group_id = handlers.get_settings().admin_group_id
    db.add(
        Document(
            file_id="f",
            file_unique_id="u",
            file_name="policy.txt",
            admin_chat_id=admin_group_id,
            status="indexed",
        )
    )
    db.commit()
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(handlers, "send_message", fake_send_message)

    await handlers.handle_update(
        {"message": {"chat": {"id": admin_group_id, "type": "group"}, "text": "/status"}},
        db,
    )

    assert sent == [(admin_group_id, "5 file gần nhất:\n#1 policy.txt - indexed")]


@pytest.mark.asyncio
async def test_admin_retry_failed_document_enqueues_task(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin_group_id = handlers.get_settings().admin_group_id
    document = Document(
        file_id="f",
        file_unique_id="u",
        file_name="policy.txt",
        admin_chat_id=admin_group_id,
        status="failed",
        error_message="old",
    )
    db.add(document)
    db.commit()
    sent = []
    enqueued = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    class FakeTask:
        def delay(self, document_id):
            enqueued.append(document_id)

    monkeypatch.setattr(handlers, "send_message", fake_send_message)
    monkeypatch.setattr(handlers, "ingest_document", FakeTask())

    await handlers.handle_update(
        {"message": {"chat": {"id": admin_group_id, "type": "group"}, "text": "/retry 1"}},
        db,
    )

    db.refresh(document)
    assert document.status == "queued"
    assert document.error_message is None
    assert enqueued == [1]
    assert sent == [(admin_group_id, "Đã enqueue retry document #1: policy.txt")]
