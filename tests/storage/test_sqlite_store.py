from datetime import datetime, timezone
from pathlib import Path

from second_brain.models import Chunk, Document, FeedSubscription
from second_brain.storage import sqlite_store


def test_insert_document_persists_document_and_chunks(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello world")
    chunks = [
        Chunk(id="chunk-1", document_id="doc-1", content="hello", chunk_index=0),
        Chunk(id="chunk-2", document_id="doc-1", content="world", chunk_index=1),
    ]

    sqlite_store.insert_document(document, chunks, db_path=db_path)

    conn = sqlite_store._connect(db_path)
    try:
        doc_row = conn.execute("SELECT id, title FROM documents WHERE id = ?", (document.id,)).fetchone()
        chunk_rows = conn.execute(
            "SELECT id, chunk_index FROM chunks WHERE document_id = ? ORDER BY chunk_index", (document.id,)
        ).fetchall()
    finally:
        conn.close()

    assert doc_row == (document.id, document.title)
    assert chunk_rows == [("chunk-1", 0), ("chunk-2", 1)]


def test_get_document_returns_none_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"

    assert sqlite_store.get_document("nope", db_path=db_path) is None


def test_get_document_round_trips(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(
        id="doc-1", source_path="/tmp/note.md", title="note", content="hello world", tags=["greeting"]
    )
    sqlite_store.insert_document(document, [], db_path=db_path)

    fetched = sqlite_store.get_document("doc-1", db_path=db_path)

    assert fetched is not None
    assert fetched.id == document.id
    assert fetched.title == document.title
    assert fetched.content == document.content
    assert fetched.tags == ["greeting"]


def test_get_document_defaults_to_empty_tags_when_not_given(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    sqlite_store.insert_document(document, [], db_path=db_path)

    fetched = sqlite_store.get_document("doc-1", db_path=db_path)

    assert fetched.tags == []


def test_get_document_by_source_path(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    sqlite_store.insert_document(document, [], db_path=db_path)

    assert sqlite_store.get_document_by_source_path("/tmp/note.md", db_path=db_path).id == "doc-1"
    assert sqlite_store.get_document_by_source_path("/tmp/missing.md", db_path=db_path) is None


def test_list_documents_includes_chunk_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    doc_a = Document(id="doc-a", source_path="/tmp/a.md", title="A", content="a", tags=["x", "y"])
    doc_b = Document(id="doc-b", source_path="/tmp/b.md", title="B", content="b")
    sqlite_store.insert_document(
        doc_a, [Chunk(id="c1", document_id="doc-a", content="x", chunk_index=0)], db_path=db_path
    )
    sqlite_store.insert_document(doc_b, [], db_path=db_path)

    summaries = sqlite_store.list_documents(db_path=db_path)

    assert [s.id for s in summaries] == ["doc-a", "doc-b"]
    assert [s.chunk_count for s in summaries] == [1, 0]
    assert [s.tags for s in summaries] == [["x", "y"], []]


def test_delete_document_removes_document_and_chunks(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    chunks = [Chunk(id="c1", document_id="doc-1", content="hello", chunk_index=0)]
    sqlite_store.insert_document(document, chunks, db_path=db_path)

    assert sqlite_store.get_chunk_ids("doc-1", db_path=db_path) == ["c1"]

    sqlite_store.delete_document("doc-1", db_path=db_path)

    assert sqlite_store.get_document("doc-1", db_path=db_path) is None
    assert sqlite_store.get_chunk_ids("doc-1", db_path=db_path) == []


def test_get_document_by_content(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello world")
    sqlite_store.insert_document(document, [], db_path=db_path)

    assert sqlite_store.get_document_by_content("hello world", db_path=db_path).id == "doc-1"
    assert sqlite_store.get_document_by_content("nope", db_path=db_path) is None


def test_delete_all_documents_removes_everything(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    doc_a = Document(id="doc-a", source_path="/tmp/a.md", title="A", content="a")
    doc_b = Document(id="doc-b", source_path="/tmp/b.md", title="B", content="b")
    sqlite_store.insert_document(
        doc_a, [Chunk(id="c1", document_id="doc-a", content="x", chunk_index=0)], db_path=db_path
    )
    sqlite_store.insert_document(doc_b, [], db_path=db_path)

    sqlite_store.delete_all_documents(db_path=db_path)

    assert sqlite_store.list_documents(db_path=db_path) == []
    assert sqlite_store.get_chunk_ids("doc-a", db_path=db_path) == []


def test_insert_feed_subscription_round_trips(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    feed = FeedSubscription(id="feed-1", url="https://example.com/rss.xml", name="Example Feed")

    sqlite_store.insert_feed_subscription(feed, db_path=db_path)
    fetched = sqlite_store.get_feed_subscription_by_url("https://example.com/rss.xml", db_path=db_path)

    assert fetched is not None
    assert fetched.id == "feed-1"
    assert fetched.name == "Example Feed"
    assert fetched.last_synced_at is None


def test_get_feed_subscription_by_url_returns_none_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"

    assert sqlite_store.get_feed_subscription_by_url("https://nope.example.com", db_path=db_path) is None


def test_list_feed_subscriptions_orders_by_added_at(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    feed_a = FeedSubscription(id="feed-a", url="https://a.example.com/rss.xml", name="A")
    feed_b = FeedSubscription(id="feed-b", url="https://b.example.com/rss.xml", name="B")
    sqlite_store.insert_feed_subscription(feed_a, db_path=db_path)
    sqlite_store.insert_feed_subscription(feed_b, db_path=db_path)

    subscriptions = sqlite_store.list_feed_subscriptions(db_path=db_path)

    assert [s.id for s in subscriptions] == ["feed-a", "feed-b"]


def test_update_feed_last_synced(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    feed = FeedSubscription(id="feed-1", url="https://example.com/rss.xml", name="Example Feed")
    sqlite_store.insert_feed_subscription(feed, db_path=db_path)
    synced_at = datetime(2026, 7, 12, 9, 0, tzinfo=timezone.utc)

    sqlite_store.update_feed_last_synced("https://example.com/rss.xml", synced_at, db_path=db_path)

    fetched = sqlite_store.get_feed_subscription_by_url("https://example.com/rss.xml", db_path=db_path)
    assert fetched.last_synced_at == synced_at


def test_delete_feed_subscription(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    feed = FeedSubscription(id="feed-1", url="https://example.com/rss.xml", name="Example Feed")
    sqlite_store.insert_feed_subscription(feed, db_path=db_path)

    sqlite_store.delete_feed_subscription("https://example.com/rss.xml", db_path=db_path)

    assert sqlite_store.get_feed_subscription_by_url("https://example.com/rss.xml", db_path=db_path) is None
