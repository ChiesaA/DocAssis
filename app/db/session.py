from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_document_admin_chat_id_column()


def ensure_document_admin_chat_id_column() -> None:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS admin_chat_id BIGINT"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
