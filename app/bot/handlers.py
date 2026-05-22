import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin.commands import HELP_TEXT, format_status_message, parse_admin_command
from app.bot.telegram import send_message
from app.config import get_settings
from app.db.models import Document, User
from app.rag.llm import embed_texts, generate_answer
from app.rag.parsers import is_supported_file
from app.rag.vector_store import search_contexts
from app.tasks.worker import ingest_document


NO_CONTEXT_MESSAGE = "Chưa tìm thấy thông tin phù hợp."
UNAUTHORIZED_MESSAGE = "Bạn chưa được cấp quyền sử dụng bot này."
ERROR_MESSAGE = "Đang có lỗi xử lý câu hỏi. Vui lòng thử lại sau."
logger = logging.getLogger(__name__)


async def handle_update(update: dict, db: Session) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    settings = get_settings()
    logger.info(
        "Received Telegram update chat_id=%s chat_type=%s has_document=%s has_text=%s",
        chat_id,
        chat_type,
        bool(message.get("document")),
        bool(message.get("text")),
    )

    if chat_id == settings.admin_group_id:
        await _handle_admin_message(message, db)
        return

    if chat_type == "private":
        await _handle_private_message(message, db)


async def _handle_admin_message(message: dict, db: Session) -> None:
    chat_id = message.get("chat", {}).get("id")
    if chat_id is None:
        return

    command = parse_admin_command(message.get("text"))
    if command:
        name, args = command
        if name == "help":
            await send_message(chat_id, HELP_TEXT)
            return
        if name == "status":
            documents = db.execute(select(Document).order_by(Document.id.desc()).limit(5)).scalars().all()
            await send_message(chat_id, format_status_message(documents))
            return

    document = message.get("document")
    if not document:
        return

    file_name = document.get("file_name", "")
    if not is_supported_file(file_name):
        await send_message(chat_id, "Chỉ hỗ trợ file PDF, TXT hoặc DOCX.")
        return

    db_document = Document(
        file_id=document["file_id"],
        file_unique_id=document["file_unique_id"],
        file_name=file_name,
        mime_type=document.get("mime_type"),
        admin_chat_id=chat_id,
        uploaded_by=(message.get("from") or {}).get("id"),
        status="queued",
    )
    db.add(db_document)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        await send_message(chat_id, f"File đã tồn tại: {file_name}")
        return

    ingest_document.delay(db_document.id)
    await send_message(chat_id, f"Đã nhận file: {file_name}. Đang xử lý.")


async def _handle_private_message(message: dict, db: Session) -> None:
    chat_id = message.get("chat", {}).get("id")
    user_id = (message.get("from") or {}).get("id")
    question = (message.get("text") or "").strip()
    if chat_id is None or user_id is None or not question:
        return

    user = db.execute(select(User).where(User.telegram_user_id == user_id)).scalar_one_or_none()
    if not user or not user.is_active:
        await send_message(chat_id, UNAUTHORIZED_MESSAGE)
        return

    settings = get_settings()
    try:
        query_vector = embed_texts([question])[0]
        contexts = search_contexts(
            query_vector,
            limit=settings.retrieval_limit,
            score_threshold=settings.retrieval_score_threshold,
        )
    except Exception:
        logger.exception("Failed to process private question for telegram_user_id=%s", user_id)
        await send_message(chat_id, ERROR_MESSAGE)
        return
    if not contexts:
        await send_message(chat_id, NO_CONTEXT_MESSAGE)
        return

    answer = generate_answer(question, contexts)
    sources = _format_sources(contexts)
    await send_message(chat_id, f"{answer}\n\nNguồn:\n{sources}")


def _format_sources(contexts: list[dict]) -> str:
    seen: set[tuple[str, int | None]] = set()
    lines: list[str] = []
    for context in contexts:
        key = (context.get("file_name"), context.get("page_number"))
        if key in seen:
            continue
        seen.add(key)
        page = f", trang {key[1]}" if key[1] else ""
        lines.append(f"- {key[0]}{page}")
    return "\n".join(lines)
