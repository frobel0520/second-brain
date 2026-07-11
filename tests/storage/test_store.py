from pathlib import Path

import pytest

from second_brain.models import Chunk, Document
from second_brain.storage import sqlite_store, store, vector_store


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)
    yield
    monkeypatch.setattr(vector_store, "_client", None)


def _document_with_chunk(doc_id: str, source_path: str, title: str) -> tuple[Document, list[Chunk]]:
    document = Document(id=doc_id, source_path=source_path, title=title, content="內容")
    chunks = [Chunk(id=f"{doc_id}-chunk", document_id=doc_id, content="內容", chunk_index=0, embedding=[0.1, 0.2])]
    return document, chunks


def test_list_documents_reflects_saved_documents() -> None:
    document, chunks = _document_with_chunk("doc-1", "/tmp/note.md", "筆記")
    store.save_document(document, chunks)

    summaries = store.list_documents()

    assert len(summaries) == 1
    assert summaries[0].title == "筆記"
    assert summaries[0].chunk_count == 1


def test_replace_existing_document_returns_none_when_no_prior_version() -> None:
    assert store.replace_existing_document("/tmp/new.md") is None


def test_replace_existing_document_removes_old_sqlite_and_chroma_rows() -> None:
    old_document, old_chunks = _document_with_chunk("doc-1", "/tmp/note.md", "舊版本")
    store.save_document(old_document, old_chunks)

    replaced_title = store.replace_existing_document("/tmp/note.md")

    assert replaced_title == "舊版本"
    assert store.list_documents() == []
    assert vector_store._get_collection().count() == 0


def test_remove_document_returns_none_when_not_found() -> None:
    assert store.remove_document("/tmp/missing.md") is None


def test_remove_document_removes_sqlite_and_chroma_rows() -> None:
    document, chunks = _document_with_chunk("doc-1", "/tmp/note.md", "筆記")
    store.save_document(document, chunks)

    removed_title = store.remove_document("/tmp/note.md")

    assert removed_title == "筆記"
    assert store.list_documents() == []
    assert vector_store._get_collection().count() == 0
