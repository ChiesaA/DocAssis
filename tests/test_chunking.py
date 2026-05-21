import pytest

from app.rag.chunking import chunk_pages


def test_chunk_pages_preserves_page_numbers_and_indexes():
    chunks = chunk_pages([(3, "abcdefghij")], chunk_size=4, chunk_overlap=1)

    assert [chunk.text for chunk in chunks] == ["abcd", "defg", "ghij", "j"]
    assert [chunk.page_number for chunk in chunks] == [3, 3, 3, 3]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2, 3]


def test_chunk_pages_rejects_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_pages([(None, "abc")], chunk_size=10, chunk_overlap=10)
