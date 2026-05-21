# DocAssis Telegram RAG Chatbot MVP

MVP chatbot nội bộ dùng một Telegram bot:

- Admin upload PDF/TXT/DOCX trong `ADMIN_GROUP_ID`.
- Worker tải file từ Telegram về `/tmp`, parse, index vào Qdrant, rồi xóa file tạm.
- PostgreSQL chỉ lưu metadata và Telegram `file_id`/`file_unique_id`.
- User private chat chỉ được hỏi khi có trong bảng `users` và `is_active = true`.
- Bot chỉ trả lời dựa trên context từ Qdrant; không có context thì trả `Chưa tìm thấy thông tin phù hợp.`

Không có dashboard, OCR, MinIO hay Kubernetes.

## Chạy local

```bash
cp .env.example .env
```

Sửa `.env`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `ADMIN_GROUP_ID`
- `OPENAI_API_KEY`

Start stack:

```bash
docker compose up --build
```

API chạy ở `http://localhost:8000`.

## Set Telegram webhook

Localhost cần tunnel như ngrok hoặc Cloudflare Tunnel.

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=https://your-public-url/telegram/webhook" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

## Cấp quyền user

Lấy Telegram user id, rồi chạy:

```bash
docker compose exec postgres psql -U docassis -d docassis \
  -c "insert into users (telegram_user_id, is_active) values (123456789, true) on conflict (telegram_user_id) do update set is_active = true;"
```

## Admin upload

Thêm bot vào admin group, cấu hình đúng `ADMIN_GROUP_ID`, rồi upload file `.pdf`, `.txt`, hoặc `.docx`.

Trạng thái document:

```bash
docker compose exec postgres psql -U docassis -d docassis \
  -c "select id, file_name, status, error_message from documents order by id desc limit 10;"
```

## Test

Chạy unit tests trong container:

```bash
docker compose run --rm api pytest -q
```

Hoặc chạy import smoke test:

```bash
docker compose run --rm api python -c "from app.main import app; print(app.title)"
```

## Ghi chú vận hành MVP

- Bảng được tạo bằng `Base.metadata.create_all()` khi API start. Với production nên thay bằng migration tool như Alembic.
- File gốc không được lưu trong hệ thống; worker chỉ dùng file tạm trong `/tmp`.
- Qdrant collection được tạo tự động khi document đầu tiên được index.
- Bot bỏ qua message từ group không phải `ADMIN_GROUP_ID`.
