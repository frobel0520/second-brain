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


def _document_with_chunk(
    doc_id: str, source_path: str, title: str, content: str = "內容"
) -> tuple[Document, list[Chunk]]:
    document = Document(id=doc_id, source_path=source_path, title=title, content=content)
    chunks = [Chunk(id=f"{doc_id}-chunk", document_id=doc_id, content=content, chunk_index=0, embedding=[0.1, 0.2])]
    return document, chunks


def test_list_documents_reflects_saved_documents() -> None:
    document, chunks = _document_with_chunk("doc-1", "/tmp/note.md", "筆記")
    store.save_document(document, chunks)

    summaries = store.list_documents()

    assert len(summaries) == 1
    assert summaries[0].title == "筆記"
    assert summaries[0].chunk_count == 1


def test_replace_existing_document_returns_none_when_no_prior_version() -> None:
    assert store.replace_existing_document("/tmp/new.md", "內容") is None


def test_replace_existing_document_matches_by_path_when_content_changed() -> None:
    old_document, old_chunks = _document_with_chunk("doc-1", "/tmp/note.md", "舊版本", content="舊內容")
    store.save_document(old_document, old_chunks)

    replaced = store.replace_existing_document("/tmp/note.md", "新內容")

    assert replaced is not None
    assert replaced.title == "舊版本"
    assert store.list_documents() == []
    assert vector_store._get_collection().count() == 0


def test_replace_existing_document_matches_by_content_when_path_changed() -> None:
    """檔案改名/搬家:路徑變了但內容沒變,應該還是能比對到舊版本。"""
    old_document, old_chunks = _document_with_chunk(
        "doc-1", "/old/path/note.md", "筆記", content="相同內容"
    )
    store.save_document(old_document, old_chunks)

    replaced = store.replace_existing_document("/new/path/note.md", "相同內容")

    assert replaced is not None
    assert replaced.source_path == "/old/path/note.md"
    assert store.list_documents() == []
    assert vector_store._get_collection().count() == 0


def test_replace_existing_document_does_not_match_different_path_and_content() -> None:
    document, chunks = _document_with_chunk("doc-1", "/tmp/a.md", "A", content="內容A")
    store.save_document(document, chunks)

    assert store.replace_existing_document("/tmp/b.md", "內容B") is None
    assert len(store.list_documents()) == 1


def test_remove_document_returns_none_when_not_found() -> None:
    assert store.remove_document("/tmp/missing.md") is None


def test_remove_document_removes_sqlite_and_chroma_rows() -> None:
    document, chunks = _document_with_chunk("doc-1", "/tmp/note.md", "筆記")
    store.save_document(document, chunks)

    removed_title = store.remove_document("/tmp/note.md")

    assert removed_title == "筆記"
    assert store.list_documents() == []
    assert vector_store._get_collection().count() == 0


def test_clear_all_returns_zero_when_empty() -> None:
    assert store.clear_all() == 0


def test_clear_all_removes_every_document_and_chunk() -> None:
    doc_a, chunks_a = _document_with_chunk("doc-a", "/tmp/a.md", "A", content="內容A")
    doc_b, chunks_b = _document_with_chunk("doc-b", "/tmp/b.md", "B", content="內容B")
    store.save_document(doc_a, chunks_a)
    store.save_document(doc_b, chunks_b)

    removed_count = store.clear_all()

    assert removed_count == 2
    assert store.list_documents() == []
    assert vector_store._get_collection().count() == 0


def test_subscribe_feed_creates_new_subscription() -> None:
    feed = store.subscribe_feed("https://example.com/rss.xml", "Example Feed")

    assert feed is not None
    assert feed.name == "Example Feed"
    assert store.list_feed_subscriptions() == [feed]


def test_subscribe_feed_returns_none_when_already_subscribed() -> None:
    store.subscribe_feed("https://example.com/rss.xml", "Example Feed")

    assert store.subscribe_feed("https://example.com/rss.xml", "Example Feed") is None
    assert len(store.list_feed_subscriptions()) == 1


def test_unsubscribe_feed_returns_none_when_not_found() -> None:
    assert store.unsubscribe_feed("https://nope.example.com") is None


def test_unsubscribe_feed_removes_subscription() -> None:
    store.subscribe_feed("https://example.com/rss.xml", "Example Feed")

    removed = store.unsubscribe_feed("https://example.com/rss.xml")

    assert removed is not None
    assert removed.name == "Example Feed"
    assert store.list_feed_subscriptions() == []


def test_mark_feed_synced_sets_last_synced_at() -> None:
    store.subscribe_feed("https://example.com/rss.xml", "Example Feed")

    store.mark_feed_synced("https://example.com/rss.xml")

    subscriptions = store.list_feed_subscriptions()
    assert subscriptions[0].last_synced_at is not None
