from pathlib import Path

import pytest

from second_brain.models import Document
from second_brain.processing import embedding as embedding_module
from second_brain.processing.chunking import chunk_document
from second_brain.processing.embedding import EmbeddingProvider
from second_brain.retrieval.search import search
from second_brain.storage import sqlite_store, store, vector_store


class _FakeEmbeddingProvider(EmbeddingProvider):
    """回傳可預期的固定向量,測試不需要載入真的模型。"""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "貓" in text else [0.0, 1.0] for text in texts]


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", _FakeEmbeddingProvider())
    yield
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", None)


def _add(document: Document) -> None:
    chunks = chunk_document(document)
    provider = embedding_module.get_embedding_provider()
    embeddings = provider.embed([chunk.content for chunk in chunks])
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb
    store.save_document(document, chunks)


def test_search_ranks_most_similar_document_first() -> None:
    cat_doc = Document(id="doc-cat", source_path="/tmp/cat.md", title="貓咪筆記", content="這是一篇關於貓的筆記。")
    dog_doc = Document(id="doc-dog", source_path="/tmp/dog.md", title="狗狗筆記", content="這是一篇關於狗的筆記。")
    _add(cat_doc)
    _add(dog_doc)

    results = search("貓在哪裡", top_k=1)

    assert len(results) == 1
    assert results[0].document.id == "doc-cat"
    assert results[0].document.title == "貓咪筆記"


def test_search_returns_empty_list_when_nothing_stored() -> None:
    assert search("隨便問問") == []
