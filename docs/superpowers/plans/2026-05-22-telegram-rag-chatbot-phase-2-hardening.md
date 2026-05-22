# Telegram RAG Chatbot Phase 2 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current Telegram RAG MVP easier to operate and safer to demo by adding admin commands, retry support, deterministic re-indexing, better health checks, and focused tests without adding a dashboard or new infrastructure.

**Architecture:** Keep the existing FastAPI webhook, PostgreSQL metadata, Redis/Celery worker, Qdrant vector store, and Gemini-backed RAG pipeline. Add small service functions around existing handlers/worker code so admin operations are testable and the webhook remains thin.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, psycopg, Celery, Redis, Qdrant, Google Gemini API via current `app/rag/llm.py`, pytest, Docker Compose.

---

## Scope

Implement Phase 2 as a hardening pass only:

- Add admin commands: `/help`, `/status`, `/retry <document_id>`.
- Improve duplicate upload behavior by status.
- Delete old Qdrant vectors for a document before re-indexing.
- Add health details for DB, Redis, and Qdrant.
- Reduce token leakage in logs by quieting noisy HTTP client logs.
- Add tests for each behavior.

Do not add a dashboard, OCR, MinIO, Kubernetes, new file storage, user management UI, or a second bot.

## File Structure

- Modify `app/db/models.py`: add retry metadata fields if needed.
- Modify `app/db/session.py`: add MVP-safe `ALTER TABLE` bootstrap for any new columns.
- Create `app/admin/__init__.py`: package marker.
- Create `app/admin/commands.py`: parse and execute admin text commands.
- Modify `app/bot/handlers.py`: route admin text commands before document handling.
- Modify `app/rag/vector_store.py`: add `delete_document_vectors(document_id)`.
- Modify `app/tasks/worker.py`: delete old vectors before upsert, preserve retry status transitions, and notify admin.
- Modify `app/main.py`: add detailed `/health` result and logging level cleanup.
- Modify `README.md`: document admin commands, retry flow, and health endpoint.
- Test `tests/test_admin_commands.py`: admin command unit tests.
- Test `tests/test_vector_store.py`: Qdrant deletion wrapper tests with monkeypatches.
- Test `tests/test_handlers.py`: duplicate upload policy tests.
- Test `tests/test_health.py`: health endpoint tests with monkeypatches or direct helper tests.

## Task 1: Admin Command Parser and Help

**Files:**
- Create: `app/admin/__init__.py`
- Create: `app/admin/commands.py`
- Modify: `app/bot/handlers.py`
- Test: `tests/test_admin_commands.py`

- [ ] **Step 1: Write failing tests for command parsing**

Create `tests/test_admin_commands.py` with:

```python
from app.admin.commands import parse_admin_command


def test_parse_help_command():
    assert parse_admin_command("/help") == ("help", [])


def test_parse_status_command():
    assert parse_admin_command("/status") == ("status", [])


def test_parse_retry_command_with_document_id():
    assert parse_admin_command("/retry 12") == ("retry", ["12"])


def test_parse_non_command_returns_none():
    assert parse_admin_command("hello") is None
```

- [ ] **Step 2: Run parser tests and verify failure**

Run:

```bash
docker compose run --rm api pytest tests/test_admin_commands.py -q
```

Expected: FAIL because `app.admin.commands` does not exist.

- [ ] **Step 3: Implement parser and help text**

Create `app/admin/__init__.py`:

```python
"""Admin command helpers."""
```

Create `app/admin/commands.py`:

```python
HELP_TEXT = (
    "Lệnh admin:\n"
    "/help - xem hướng dẫn\n"
    "/status - xem 5 file gần nhất\n"
    "/retry <document_id> - xử lý lại file failed"
)


def parse_admin_command(text: str | None) -> tuple[str, list[str]] | None:
    value = (text or "").strip()
    if not value.startswith("/"):
        return None
    parts = value.split()
    command = parts[0].split("@", 1)[0].lower().lstrip("/")
    if command not in {"help", "status", "retry"}:
        return None
    return command, parts[1:]
```

- [ ] **Step 4: Run parser tests and verify pass**

Run:

```bash
docker compose run --rm api pytest tests/test_admin_commands.py -q
```

Expected: PASS.

- [ ] **Step 5: Wire `/help` into admin flow**

Modify `app/bot/handlers.py` so `_handle_admin_message()` checks text commands before document handling:

```python
from app.admin.commands import HELP_TEXT, parse_admin_command
```

Inside `_handle_admin_message()` before reading `document`:

```python
    command = parse_admin_command(message.get("text"))
    if command:
        name, args = command
        if name == "help":
            await send_message(chat_id, HELP_TEXT)
            return
```

Keep `args` unused for now if only `/help` is wired in this task.

- [ ] **Step 6: Add handler test for `/help`**

Append to `tests/test_admin_commands.py`:

```python
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

from app.admin.commands import HELP_TEXT
from app.bot import handlers
from app.db.models import Base


@pytest.mark.asyncio
async def test_admin_help_command_sends_help(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(handlers, "send_message", fake_send_message)

    await handlers.handle_update(
        {"message": {"chat": {"id": -100, "type": "group"}, "text": "/help"}},
        db,
    )

    assert sent == [(-100, HELP_TEXT)]
```

- [ ] **Step 7: Run command tests**

Run:

```bash
docker compose run --rm api pytest tests/test_admin_commands.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit task**

```bash
git add app/admin app/bot/handlers.py tests/test_admin_commands.py
git commit -m "feat: add admin help command"
```

## Task 2: `/status` Admin Command

**Files:**
- Modify: `app/admin/commands.py`
- Modify: `app/bot/handlers.py`
- Test: `tests/test_admin_commands.py`

- [ ] **Step 1: Write failing tests for status formatting**

Append to `tests/test_admin_commands.py`:

```python
from app.admin.commands import format_status_message
from app.db.models import Document


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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
docker compose run --rm api pytest tests/test_admin_commands.py::test_format_status_message_lists_recent_documents tests/test_admin_commands.py::test_format_status_message_handles_empty_list -q
```

Expected: FAIL because `format_status_message` does not exist.

- [ ] **Step 3: Implement status formatter**

Add to `app/admin/commands.py`:

```python
def format_status_message(documents) -> str:
    if not documents:
        return "Chưa có file nào."
    lines = ["5 file gần nhất:"]
    for document in documents:
        line = f"#{document.id} {document.file_name} - {document.status}"
        if document.status == "failed" and document.error_message:
            line = f"{line} - {document.error_message[:120]}"
        lines.append(line)
    return "\n".join(lines)
```

- [ ] **Step 4: Wire `/status` in handler**

In `app/bot/handlers.py`, import `format_status_message` and `select(Document)` if not already available. In the command block:

```python
        if name == "status":
            documents = db.execute(select(Document).order_by(Document.id.desc()).limit(5)).scalars().all()
            await send_message(chat_id, format_status_message(documents))
            return
```

- [ ] **Step 5: Add handler test**

Append:

```python
@pytest.mark.asyncio
async def test_admin_status_command_sends_recent_documents(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Document(file_id="f", file_unique_id="u", file_name="policy.txt", admin_chat_id=-100, status="indexed"))
    db.commit()
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(handlers, "send_message", fake_send_message)

    await handlers.handle_update(
        {"message": {"chat": {"id": -100, "type": "group"}, "text": "/status"}},
        db,
    )

    assert sent == [(-100, "5 file gần nhất:\n#1 policy.txt - indexed")]
```

- [ ] **Step 6: Run tests**

Run:

```bash
docker compose run --rm api pytest tests/test_admin_commands.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit task**

```bash
git add app/admin/commands.py app/bot/handlers.py tests/test_admin_commands.py
git commit -m "feat: add admin status command"
```

## Task 3: Retry Failed Documents

**Files:**
- Modify: `app/admin/commands.py`
- Modify: `app/bot/handlers.py`
- Modify: `app/tasks/worker.py`
- Test: `tests/test_admin_commands.py`

- [ ] **Step 1: Write failing tests for retry validation messages**

Append:

```python
from app.admin.commands import build_retry_response


def test_build_retry_response_requires_numeric_id():
    assert build_retry_response([]) == (None, "Dùng: /retry <document_id>")
    assert build_retry_response(["abc"]) == (None, "document_id phải là số.")


def test_build_retry_response_accepts_numeric_id():
    assert build_retry_response(["42"]) == (42, "")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
docker compose run --rm api pytest tests/test_admin_commands.py::test_build_retry_response_requires_numeric_id tests/test_admin_commands.py::test_build_retry_response_accepts_numeric_id -q
```

Expected: FAIL because `build_retry_response` does not exist.

- [ ] **Step 3: Implement retry argument parser**

Add to `app/admin/commands.py`:

```python
def build_retry_response(args: list[str]) -> tuple[int | None, str]:
    if not args:
        return None, "Dùng: /retry <document_id>"
    try:
        return int(args[0]), ""
    except ValueError:
        return None, "document_id phải là số."
```

- [ ] **Step 4: Wire `/retry` in handler**

In `app/bot/handlers.py`, import `build_retry_response`. In the command block:

```python
        if name == "retry":
            document_id, error = build_retry_response(args)
            if error:
                await send_message(chat_id, error)
                return
            document = db.get(Document, document_id)
            if not document:
                await send_message(chat_id, f"Không tìm thấy document #{document_id}.")
                return
            if document.status not in {"failed", "indexed"}:
                await send_message(chat_id, f"Document #{document_id} đang ở trạng thái {document.status}, chưa thể retry.")
                return
            document.status = "queued"
            document.error_message = None
            document.admin_chat_id = chat_id
            db.commit()
            ingest_document.delay(document.id)
            await send_message(chat_id, f"Đã enqueue retry document #{document.id}: {document.file_name}")
            return
```

- [ ] **Step 5: Add handler tests for retry**

Append:

```python
@pytest.mark.asyncio
async def test_admin_retry_failed_document_enqueues_task(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    document = Document(file_id="f", file_unique_id="u", file_name="policy.txt", admin_chat_id=-100, status="failed", error_message="old")
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
        {"message": {"chat": {"id": -100, "type": "group"}, "text": "/retry 1"}},
        db,
    )

    db.refresh(document)
    assert document.status == "queued"
    assert document.error_message is None
    assert enqueued == [1]
    assert sent == [(-100, "Đã enqueue retry document #1: policy.txt")]
```

- [ ] **Step 6: Run admin command tests**

Run:

```bash
docker compose run --rm api pytest tests/test_admin_commands.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit task**

```bash
git add app/admin/commands.py app/bot/handlers.py tests/test_admin_commands.py
git commit -m "feat: add admin retry command"
```

## Task 4: Duplicate Upload Policy

**Files:**
- Modify: `app/bot/handlers.py`
- Test: `tests/test_handlers.py`

- [ ] **Step 1: Write failing tests for duplicate behavior**

Append to `tests/test_handlers.py`:

```python
from app.db.models import Document


@pytest.mark.asyncio
async def test_admin_duplicate_indexed_file_reports_existing(monkeypatch, db):
    db.add(Document(file_id="old", file_unique_id="same", file_name="policy.txt", admin_chat_id=-100, status="indexed"))
    db.commit()
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(handlers, "send_message", fake_send_message)

    await handlers.handle_update(
        {
            "message": {
                "chat": {"id": -100, "type": "group"},
                "from": {"id": 20},
                "document": {"file_id": "new", "file_unique_id": "same", "file_name": "policy.txt"},
            }
        },
        db,
    )

    assert sent == [(-100, "File đã được index: policy.txt")]


@pytest.mark.asyncio
async def test_admin_duplicate_failed_file_suggests_retry(monkeypatch, db):
    db.add(Document(file_id="old", file_unique_id="same", file_name="policy.txt", admin_chat_id=-100, status="failed"))
    db.commit()
    sent = []

    async def fake_send_message(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(handlers, "send_message", fake_send_message)

    await handlers.handle_update(
        {
            "message": {
                "chat": {"id": -100, "type": "group"},
                "from": {"id": 20},
                "document": {"file_id": "new", "file_unique_id": "same", "file_name": "policy.txt"},
            }
        },
        db,
    )

    assert sent == [(-100, "File từng xử lý lỗi: policy.txt. Dùng /retry 1 để xử lý lại.")]
```

- [ ] **Step 2: Run duplicate tests and verify failure**

Run:

```bash
docker compose run --rm api pytest tests/test_handlers.py::test_admin_duplicate_indexed_file_reports_existing tests/test_handlers.py::test_admin_duplicate_failed_file_suggests_retry -q
```

Expected: FAIL with old duplicate message.

- [ ] **Step 3: Replace IntegrityError-only duplicate handling with pre-check**

In `_handle_admin_message()` before creating `Document`:

```python
    existing = db.execute(select(Document).where(Document.file_unique_id == document["file_unique_id"])).scalar_one_or_none()
    if existing:
        if existing.status == "indexed":
            await send_message(chat_id, f"File đã được index: {existing.file_name}")
            return
        if existing.status == "failed":
            await send_message(chat_id, f"File từng xử lý lỗi: {existing.file_name}. Dùng /retry {existing.id} để xử lý lại.")
            return
        await send_message(chat_id, f"File đang ở trạng thái {existing.status}: {existing.file_name}")
        return
```

Keep the `IntegrityError` fallback for race conditions.

- [ ] **Step 4: Run handler tests**

Run:

```bash
docker compose run --rm api pytest tests/test_handlers.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit task**

```bash
git add app/bot/handlers.py tests/test_handlers.py
git commit -m "feat: improve duplicate upload handling"
```

## Task 5: Delete Old Vectors Before Re-index

**Files:**
- Modify: `app/rag/vector_store.py`
- Modify: `app/tasks/worker.py`
- Test: `tests/test_vector_store.py`

- [ ] **Step 1: Write failing vector store test**

Create `tests/test_vector_store.py`:

```python
from app.rag import vector_store


def test_delete_document_vectors_uses_document_filter(monkeypatch):
    calls = []

    class FakeClient:
        def delete(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(vector_store, "client", FakeClient())

    vector_store.delete_document_vectors(42)

    assert calls
    assert calls[0]["collection_name"] == vector_store.settings.qdrant_collection
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
docker compose run --rm api pytest tests/test_vector_store.py -q
```

Expected: FAIL because `delete_document_vectors` does not exist.

- [ ] **Step 3: Implement delete function**

Add imports in `app/rag/vector_store.py`:

```python
from qdrant_client.models import FieldCondition, Filter, MatchValue
```

Add:

```python
def delete_document_vectors(document_id: int) -> None:
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
    )
```

- [ ] **Step 4: Call deletion before upsert**

In `app/tasks/worker.py`, import `delete_document_vectors`. Before `upsert_chunks(...)`:

```python
        delete_document_vectors(document.id)
```

- [ ] **Step 5: Run tests**

Run:

```bash
docker compose run --rm api pytest tests/test_vector_store.py tests/test_worker_notifications.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit task**

```bash
git add app/rag/vector_store.py app/tasks/worker.py tests/test_vector_store.py
git commit -m "feat: replace document vectors on reindex"
```

## Task 6: Detailed Health Check

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: Write failing tests for health payload helper**

Create `tests/test_health.py`:

```python
from app.main import build_health_payload


def test_build_health_payload_reports_all_dependencies_ok():
    payload = build_health_payload(db_ok=True, redis_ok=True, qdrant_ok=True)

    assert payload == {
        "status": "ok",
        "dependencies": {"database": "ok", "redis": "ok", "qdrant": "ok"},
    }


def test_build_health_payload_reports_degraded():
    payload = build_health_payload(db_ok=True, redis_ok=False, qdrant_ok=True)

    assert payload["status"] == "degraded"
    assert payload["dependencies"]["redis"] == "error"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
docker compose run --rm api pytest tests/test_health.py -q
```

Expected: FAIL because `build_health_payload` does not exist.

- [ ] **Step 3: Implement helper and basic checks**

In `app/main.py`, add:

```python
from redis import Redis
from sqlalchemy import text
from qdrant_client import QdrantClient
```

Add:

```python
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
```

Change `/health` to:

```python
@app.get("/health")
def health() -> dict:
    settings = get_settings()
    db_ok = redis_ok = qdrant_ok = False
    try:
        with next(get_db()) as db:
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
```

If using `next(get_db())` reads awkwardly, instead import `SessionLocal` and use `with SessionLocal() as db`.

- [ ] **Step 4: Run health tests**

Run:

```bash
docker compose run --rm api pytest tests/test_health.py -q
```

Expected: PASS.

- [ ] **Step 5: Smoke test health endpoint**

Run:

```bash
curl http://localhost:8000/health
```

Expected while compose is running:

```json
{"status":"ok","dependencies":{"database":"ok","redis":"ok","qdrant":"ok"}}
```

- [ ] **Step 6: Commit task**

```bash
git add app/main.py tests/test_health.py
git commit -m "feat: add dependency health checks"
```

## Task 7: Logging Cleanup

**Files:**
- Modify: `app/main.py`
- Modify: `README.md`
- Test: no new test required; verify by log inspection.

- [ ] **Step 1: Reduce noisy third-party logs**

In `app/main.py`, after `logging.basicConfig(level=logging.INFO)`:

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
```

- [ ] **Step 2: Run tests**

Run:

```bash
docker compose run --rm api pytest -q
```

Expected: PASS.

- [ ] **Step 3: Manually inspect logs**

Run:

```bash
docker compose logs --tail=80 api worker
```

Expected: no normal successful Telegram/Gemini URLs are emitted at INFO level by `httpx`.

- [ ] **Step 4: Update README operations section**

Append under "Ghi chú vận hành MVP":

```markdown
- Dùng `docker compose logs -f --tail=0 api worker` khi debug webhook để chỉ xem log mới.
- `/status` và `/retry <document_id>` chỉ hoạt động trong admin group.
```

- [ ] **Step 5: Commit task**

```bash
git add app/main.py README.md
git commit -m "chore: reduce noisy service logs"
```

## Task 8: Final Verification and Push

**Files:**
- No new files unless previous tasks require fixes.

- [ ] **Step 1: Run full test suite**

Run:

```bash
docker compose run --rm api pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Recreate runtime services**

Run:

```bash
docker compose up -d --force-recreate api worker
```

Expected: both services start.

- [ ] **Step 3: Manual admin smoke test**

In Telegram admin group:

```text
/help
/status
```

Expected: bot replies to both.

- [ ] **Step 4: Manual ingest smoke test**

Upload a small new `.txt` file in admin group.

Expected sequence:

```text
Đã nhận file: <file>. Đang xử lý.
Đã xử lý xong file: <file>. Đã index <n> đoạn nội dung.
```

- [ ] **Step 5: Manual private question smoke test**

Ask a private question related to the uploaded file.

Expected: answer includes:

```text
Nguồn:
- <file>
```

- [ ] **Step 6: Push branch**

Run:

```bash
git status --short --branch
git push origin main
```

Expected: `main` pushed to `origin/main`, working tree clean.

## Self-Review

- Spec coverage: This plan covers the Phase 2 hardening items: admin commands, retry, duplicate handling, vector replacement, health checks, logging cleanup, tests, and manual smoke tests.
- Placeholder scan: No `TODO`, `TBD`, or vague "handle errors" steps remain; each task has file paths, code snippets, commands, and expected results.
- Type consistency: New helpers use `Document`, existing `ingest_document.delay`, and current `send_message` async helper consistently.
- Scope check: No dashboard, OCR, Kubernetes, MinIO, or second bot is introduced.
