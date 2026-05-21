from pathlib import Path

import fitz
from docx import Document as DocxDocument


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}


def is_supported_file(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in SUPPORTED_EXTENSIONS


def parse_file(path: str, file_name: str) -> list[tuple[int | None, str]]:
    extension = Path(file_name).suffix.lower()
    if extension == ".txt":
        return _parse_txt(path)
    if extension == ".pdf":
        return _parse_pdf(path)
    if extension == ".docx":
        return _parse_docx(path)
    raise ValueError(f"Unsupported file extension: {extension}")


def _parse_txt(path: str) -> list[tuple[int | None, str]]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return [(None, text)]


def _parse_pdf(path: str) -> list[tuple[int | None, str]]:
    pages: list[tuple[int | None, str]] = []
    with fitz.open(path) as pdf:
        for index, page in enumerate(pdf, start=1):
            pages.append((index, page.get_text("text")))
    return pages


def _parse_docx(path: str) -> list[tuple[int | None, str]]:
    document = DocxDocument(path)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return [(None, text)]
