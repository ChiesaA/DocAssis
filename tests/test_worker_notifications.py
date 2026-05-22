from app.db.models import Document
from app.tasks.worker import build_failure_message, build_success_message, should_notify_admin


def test_should_notify_admin_requires_admin_chat_id():
    assert should_notify_admin(Document(admin_chat_id=-100, file_name="a.txt")) is True
    assert should_notify_admin(Document(admin_chat_id=None, file_name="a.txt")) is False


def test_build_success_message_reports_file_indexed():
    document = Document(file_name="policy.txt")

    assert build_success_message(document, chunk_count=3) == "Đã xử lý xong file: policy.txt. Đã index 3 đoạn nội dung."


def test_build_failure_message_reports_truncated_error():
    document = Document(file_name="policy.txt")
    message = build_failure_message(document, "x" * 500)

    assert message.startswith("Xử lý file thất bại: policy.txt.")
    assert len(message) < 420
