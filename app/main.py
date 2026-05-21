from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.bot.handlers import handle_update
from app.config import get_settings
from app.db.session import create_tables, get_db


app = FastAPI(title="DocAssis Telegram RAG Bot")


@app.on_event("startup")
def on_startup() -> None:
    create_tables()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
