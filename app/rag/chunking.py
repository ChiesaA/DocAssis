from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    page_number: int | None
    chunk_index: int


def chunk_pages(
    pages: list[tuple[int | None, str]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    chunks: list[TextChunk] = []
    chunk_index = 0
    step = chunk_size - chunk_overlap

    for page_number, text in pages:
        normalized = " ".join(text.split())
        if not normalized:
            continue

        start = 0
        while start < len(normalized):
            value = normalized[start : start + chunk_size].strip()
            if value:
                chunks.append(TextChunk(text=value, page_number=page_number, chunk_index=chunk_index))
                chunk_index += 1
            start += step

    return chunks
