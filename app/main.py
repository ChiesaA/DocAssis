import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from qdrant_client import QdrantClient
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bot.handlers import handle_update
from app.config import get_settings
from app.db.session import SessionLocal, create_tables, get_db


logging.basicConfig(level=logging.INFO)
app = FastAPI(title="DocAssis Telegram RAG Bot")


@app.on_event("startup")
def on_startup() -> None:
    create_tables()


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    db_ok = redis_ok = qdrant_ok = False
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
            db_ok = True
    except Exception:
        db_ok = False
    try:
        Redis.from_url(settings.redis_url).ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    try:
        QdrantClient(url=settings.qdrant_url).get_collections()
        qdrant_ok = True
    except Exception:
        qdrant_ok = False
    return build_health_payload(db_ok, redis_ok, qdrant_ok)


def build_health_payload(db_ok: bool, redis_ok: bool, qdrant_ok: bool) -> dict:
    dependencies = {
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "qdrant": "ok" if qdrant_ok else "error",
    }
    return {
        "status": "ok" if all([db_ok, redis_ok, qdrant_ok]) else "degraded",
        "dependencies": dependencies,
    }


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    settings = get_settings()
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    update = await request.json()
    await handle_update(update, db)
    return {"ok": True}
