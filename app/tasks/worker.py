import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.bot.telegram import download_file, send_message
from app.config import get_settings
from app.db.models import Document
from app.db.session import SessionLocal
from app.rag.chunking import chunk_pages
from app.rag.llm import embed_texts
from app.rag.parsers import parse_file
from app.rag.vector_store import upsert_chunks
from app.tasks.celery_app import celery_app


@celery_app.task(name="ingest_document")
def ingest_document(document_id: int) -> None:
    settings = get_settings()
    temp_path: str | None = None
    db = SessionLocal()
    try:
        document = db.execute(select(Document).where(Document.id == document_id)).scalar_one()
        document.status = "processing"
        document.error_message = None
        db.commit()

        suffix = Path(document.file_name).suffix
        with tempfile.NamedTemporaryFile(prefix="telegram_", suffix=suffix, delete=False) as temp_file:
            temp_path = temp_file.name

        asyncio.run(download_file(document.file_id, temp_path))
        pages = parse_file(temp_path, document.file_name)
        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        vectors = embed_texts([chunk.text for chunk in chunks])
        upsert_chunks(document.id, chunks, vectors, document.file_name)

        document.status = "indexed"
        db.commit()
        if should_notify_admin(document):
            asyncio.run(send_message(document.admin_chat_id, build_success_message(document, len(chunks))))
    except Exception as exc:
        db.rollback()
        document = db.get(Document, document_id)
        if document:
            document.status = "failed"
            document.error_message = str(exc)[:4000]
            db.commit()
            if should_notify_admin(document):
                asyncio.run(send_message(document.admin_chat_id, build_failure_message(document, str(exc))))
        raise
    finally:
        db.close()
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


def should_notify_admin(document: Document) -> bool:
    return document.admin_chat_id is not None


def build_success_message(document: Document, chunk_count: int) -> str:
    return f"Đã xử lý xong file: {document.file_name}. Đã index {chunk_count} đoạn nội dung."


def build_failure_message(document: Document, error: str) -> str:
    clipped_error = error[:300]
    return f"Xử lý file thất bại: {document.file_name}.\nLỗi: {clipped_error}"
