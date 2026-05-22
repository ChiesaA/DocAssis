from app.rag import vector_store


def test_delete_document_vectors_uses_document_filter(monkeypatch):
    calls = []

    class FakeClient:
        def delete(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(vector_store, "client", FakeClient())

    vector_store.delete_document_vectors(42)

    assert calls
    assert calls[0]["collection_name"] == vector_store.settings.qdrant_collection
