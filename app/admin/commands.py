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


def build_retry_response(args: list[str]) -> tuple[int | None, str]:
    if not args:
        return None, "Dùng: /retry <document_id>"
    try:
        return int(args[0]), ""
    except ValueError:
        return None, "document_id phải là số."
