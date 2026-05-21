# Telegram RAG Chatbot MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Docker Compose runnable internal Telegram RAG chatbot with FastAPI, Celery, PostgreSQL, Redis, Qdrant, and OpenAI.

**Architecture:** FastAPI receives Telegram webhook updates and routes admin group documents to ingestion or private messages to RAG answers. Celery downloads Telegram files temporarily, parses and chunks them, embeds chunks, and upserts Qdrant points while PostgreSQL stores users and document metadata.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, psycopg, Celery, Redis, Qdrant, OpenAI, PyMuPDF, python-docx, Docker Compose.

---

## File Structure

- `docker-compose.yml`: local API, worker, PostgreSQL, Redis, and Qdrant stack.
- `Dockerfile`: shared image for API and worker.
- `requirements.txt`: pinned runtime and test dependencies.
- `.env.example`: configuration template.
- `README.md`: setup, migration, webhook, and smoke test instructions.
- `app/config.py`: environment-driven settings.
- `app/main.py`: FastAPI app, database bootstrap, webhook route, healthcheck.
- `app/db/session.py`: SQLAlchemy engine/session helpers.
- `app/db/models.py`: `users` and `documents` models.
- `app/bot/telegram.py`: Telegram API calls.
- `app/bot/handlers.py`: admin and private message routing.
- `app/rag/parsers.py`: PDF/TXT/DOCX parsing into page-aware chunks.
- `app/rag/chunking.py`: minimal text chunking.
- `app/rag/llm.py`: OpenAI embeddings and answer generation.
- `app/rag/vector_store.py`: Qdrant collection setup, upsert, and search.
- `app/tasks/celery_app.py`: Celery app.
- `app/tasks/worker.py`: asynchronous document ingestion task.
- `tests/test_chunking.py`: chunking unit tests.
- `tests/test_handlers.py`: authorization and routing tests.

## Tasks

### Task 1: Project Foundation

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `app/__init__.py`
- Create: `app/config.py`

- [x] Add runtime dependencies and Docker Compose services.
- [x] Add settings for Telegram, PostgreSQL, Redis, Qdrant, OpenAI, retrieval threshold, and collection name.

### Task 2: Database Models

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/models.py`
- Create: `app/db/session.py`

- [x] Define `users` with `telegram_user_id` and `is_active`.
- [x] Define `documents` with Telegram file identifiers, processing status, and error message.
- [x] Provide `create_tables()` for MVP startup bootstrapping.

### Task 3: RAG Core

**Files:**
- Create: `app/rag/__init__.py`
- Create: `app/rag/chunking.py`
- Create: `app/rag/parsers.py`
- Create: `app/rag/llm.py`
- Create: `app/rag/vector_store.py`
- Create: `tests/test_chunking.py`

- [x] Implement deterministic chunking with overlap.
- [x] Parse TXT, PDF, and DOCX into page-aware text records.
- [x] Embed text and generate grounded answers with OpenAI.
- [x] Initialize, upsert, and query Qdrant.

### Task 4: Telegram Flows

**Files:**
- Create: `app/bot/__init__.py`
- Create: `app/bot/telegram.py`
- Create: `app/bot/handlers.py`
- Create: `tests/test_handlers.py`

- [x] Route admin group documents into document metadata plus Celery task.
- [x] Route private messages through active-user authorization.
- [x] Return no-context fallback when Qdrant has no sufficiently relevant hits.

### Task 5: API and Worker

**Files:**
- Create: `app/main.py`
- Create: `app/tasks/__init__.py`
- Create: `app/tasks/celery_app.py`
- Create: `app/tasks/worker.py`

- [x] Expose `/health` and `/telegram/webhook`.
- [x] Configure Celery with Redis.
- [x] Download Telegram files to `/tmp`, parse, index, update status, and delete temp files.

### Task 6: Documentation and Verification

**Files:**
- Create: `README.md`

- [x] Document `docker compose up --build`, webhook setup, admin upload, user activation SQL, and test commands.
- [x] Verify imports and tests locally.

## Self-Review

- Spec coverage: all requested MVP services and flows are covered.
- Placeholder scan: no `TODO`, `TBD`, or unspecified future work in this plan.
- Scope check: dashboard, OCR, Kubernetes, and MinIO are excluded.
