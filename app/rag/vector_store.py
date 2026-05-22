from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.config import get_settings


settings = get_settings()
client = QdrantClient(url=settings.qdrant_url)


def ensure_collection(vector_size: int) -> None:
    collections = client.get_collections().collections
    if any(collection.name == settings.qdrant_collection for collection in collections):
        return
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def upsert_chunks(document_id: int, chunks: list, vectors: list[list[float]], file_name: str) -> None:
    if not chunks or not vectors:
        return
    ensure_collection(len(vectors[0]))
    points = [
        PointStruct(
            id=str(uuid4()),
            vector=vector,
            payload={
                "document_id": document_id,
                "file_name": file_name,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points)


def delete_document_vectors(document_id: int) -> None:
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
    )


def search_contexts(query_vector: list[float], limit: int, score_threshold: float) -> list[dict]:
    try:
        results = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )
    except Exception:
        return []
    return [
        {
            "score": result.score,
            "file_name": result.payload.get("file_name"),
            "page_number": result.payload.get("page_number"),
            "text": result.payload.get("text"),
        }
        for result in results
        if result.payload and result.payload.get("text")
    ]
