# Telegram RAG Chatbot MVP Design

## Scope

Build a minimal internal Telegram RAG chatbot using Python 3.12, FastAPI, PostgreSQL, Redis, Celery, and Qdrant. The system uses one Telegram bot. It has no dashboard, OCR, Kubernetes, MinIO, or extra orchestration beyond Docker Compose.

## Architecture

The FastAPI app exposes a Telegram webhook endpoint and a healthcheck. Telegram updates are routed by chat type:

- Messages from `ADMIN_GROUP_ID` use the admin flow.
- Private chat messages use the user question flow.
- Other chats are ignored.

PostgreSQL stores users and document metadata. Redis is the Celery broker/result backend. Qdrant stores embedded text chunks. OpenAI is used for embeddings and answer generation, configured through environment variables.

## Admin Flow

Admins upload PDF, TXT, or DOCX files in the configured admin group. The bot validates the file extension, stores metadata in PostgreSQL, and enqueues a Celery task. The database stores Telegram `file_id` and `file_unique_id`, not the original file bytes.

The worker downloads the Telegram file to `/tmp`, parses it, chunks the text, embeds the chunks, upserts vectors into Qdrant, updates processing status in PostgreSQL, and deletes the temporary file.

## User Question Flow

Private users can ask questions only if a row exists in `users` with matching `telegram_user_id` and `is_active = true`.

For authorized users, the bot embeds the question, searches Qdrant, and only answers from retrieved context. If there is no sufficiently relevant context, the bot replies that no matching information was found. Answers include source metadata: `file_name` and `page_number` when available.

## Components

- `app/main.py`: FastAPI app, startup initialization, routes.
- `app/bot/telegram.py`: Telegram API helpers.
- `app/bot/handlers.py`: Telegram update routing and admin/user flows.
- `app/db/`: SQLAlchemy engine, sessions, and models.
- `app/rag/`: parsers, chunking, embeddings, vector store, answer generation.
- `app/tasks/worker.py`: Celery configuration and ingestion task.
- `docker-compose.yml`: API, worker, PostgreSQL, Redis, and Qdrant services.
- `.env.example`: required configuration.
- `README.md`: setup and run instructions.

## Error Handling

Unsupported admin files are rejected with a short Telegram message. Failed ingestion marks the document status as `failed` and stores an error message. Telegram download temp files are removed in a cleanup block. Unauthorized private users receive a denial message.

## Verification

The MVP should verify with Docker Compose startup and basic Python import checks. Manual verification covers webhook setup, admin upload ingestion, active user question answering, unauthorized user denial, and no-context fallback.
