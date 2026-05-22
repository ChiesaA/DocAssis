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
