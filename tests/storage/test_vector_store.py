from pathlib import Path

import pytest

from second_brain.models import Chunk
from second_brain.storage import vector_store


@pytest.fixture(autouse=True)
def _isolated_chroma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)
    yield
    monkeypatch.setattr(vector_store, "_client", None)


def test_add_chunks_requires_embeddings() -> None:
    chunks = [Chunk(id="c1", document_id="d1", content="hello", chunk_index=0)]

    with pytest.raises(ValueError):
        vector_store.add_chunks(chunks)


def test_add_chunks_stores_embeddings() -> None:
    chunks = [
        Chunk(id="c1", document_id="d1", content="hello", chunk_index=0, embedding=[0.1, 0.2]),
        Chunk(id="c2", document_id="d1", content="world", chunk_index=1, embedding=[0.3, 0.4]),
    ]

    vector_store.add_chunks(chunks)

    collection = vector_store._get_collection()
    assert collection.count() == 2


def test_query_similar_returns_empty_list_when_collection_is_empty() -> None:
    assert vector_store.query_similar([0.1, 0.2]) == []


def test_query_similar_ranks_closest_first() -> None:
    chunks = [
        Chunk(id="c1", document_id="d1", content="near", chunk_index=0, embedding=[1.0, 0.0]),
        Chunk(id="c2", document_id="d1", content="far", chunk_index=1, embedding=[0.0, 1.0]),
    ]
    vector_store.add_chunks(chunks)

    matches = vector_store.query_similar([0.9, 0.1], top_k=2)

    assert [m["chunk_id"] for m in matches] == ["c1", "c2"]
    assert matches[0]["content"] == "near"
    assert matches[0]["document_id"] == "d1"


def test_delete_chunks_removes_only_given_ids() -> None:
    chunks = [
        Chunk(id="c1", document_id="d1", content="a", chunk_index=0, embedding=[0.1, 0.2]),
        Chunk(id="c2", document_id="d1", content="b", chunk_index=1, embedding=[0.3, 0.4]),
    ]
    vector_store.add_chunks(chunks)

    vector_store.delete_chunks(["c1"])

    collection = vector_store._get_collection()
    assert collection.count() == 1
    assert collection.get(ids=["c2"])["ids"] == ["c2"]
