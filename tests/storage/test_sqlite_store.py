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


def test_list_all_chunks_returns_every_chunk_across_documents(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    doc_a = Document(id="doc-a", source_path="/tmp/a.md", title="a", content="hello")
    doc_b = Document(id="doc-b", source_path="/tmp/b.md", title="b", content="world")
    sqlite_store.insert_document(
        doc_a, [Chunk(id="chunk-a", document_id="doc-a", content="hello", chunk_index=0)], db_path=db_path
    )
    sqlite_store.insert_document(
        doc_b, [Chunk(id="chunk-b", document_id="doc-b", content="world", chunk_index=0)], db_path=db_path
    )

    chunks = sqlite_store.list_all_chunks(db_path=db_path)

    assert {chunk.id for chunk in chunks} == {"chunk-a", "chunk-b"}
    assert {chunk.content for chunk in chunks} == {"hello", "world"}


def test_list_all_chunks_returns_empty_list_when_nothing_stored(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"

    assert sqlite_store.list_all_chunks(db_path=db_path) == []


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


def test_ensure_translated_content_column_migrates_old_schema(tmp_path: Path) -> None:
    """模擬「在 translated_content 欄位存在之前建立的資料庫」,確認 `_connect()`
    會自動幫舊資料庫補上這個欄位,不需要使用者手動刪掉重建。"""
    import sqlite3

    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE documents (id TEXT PRIMARY KEY, source_path TEXT NOT NULL, title TEXT NOT NULL, "
        "content TEXT NOT NULL, created_at TEXT NOT NULL, metadata TEXT NOT NULL, "
        "tags TEXT NOT NULL DEFAULT '[]');"
    )
    conn.close()

    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    sqlite_store.insert_document(document, [], db_path=db_path)

    fetched = sqlite_store.get_document("doc-1", db_path=db_path)
    assert fetched.translated_content is None


def test_insert_document_persists_translated_content(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(
        id="doc-1", source_path="/tmp/note.md", title="note", content="hello", translated_content="你好"
    )

    sqlite_store.insert_document(document, [], db_path=db_path)

    fetched = sqlite_store.get_document("doc-1", db_path=db_path)
    assert fetched.translated_content == "你好"


def test_insert_document_defaults_to_not_starred(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")

    sqlite_store.insert_document(document, [], db_path=db_path)

    assert sqlite_store.get_document("doc-1", db_path=db_path).starred is False


def test_insert_document_persists_starred(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello", starred=True)

    sqlite_store.insert_document(document, [], db_path=db_path)

    assert sqlite_store.get_document("doc-1", db_path=db_path).starred is True


def test_set_document_starred_updates_existing_document(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    sqlite_store.insert_document(document, [], db_path=db_path)

    sqlite_store.set_document_starred("doc-1", True, db_path=db_path)

    assert sqlite_store.get_document("doc-1", db_path=db_path).starred is True


def test_ensure_starred_column_migrates_old_schema(tmp_path: Path) -> None:
    """模擬「在 starred 欄位存在之前建立的資料庫」,確認 `_connect()` 會自動
    補上這個欄位並預設為未加星,不需要使用者手動刪掉重建。"""
    import sqlite3

    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE documents (id TEXT PRIMARY KEY, source_path TEXT NOT NULL, title TEXT NOT NULL, "
        "content TEXT NOT NULL, created_at TEXT NOT NULL, metadata TEXT NOT NULL, "
        "tags TEXT NOT NULL DEFAULT '[]');"
    )
    conn.close()

    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    sqlite_store.insert_document(document, [], db_path=db_path)

    fetched = sqlite_store.get_document("doc-1", db_path=db_path)
    assert fetched.starred is False


def test_insert_document_persists_category(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello", category="財經")

    sqlite_store.insert_document(document, [], db_path=db_path)

    fetched = sqlite_store.get_document("doc-1", db_path=db_path)
    assert fetched.category == "財經"


def test_update_document_category_changes_existing_document(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    sqlite_store.insert_document(document, [], db_path=db_path)

    sqlite_store.update_document_category("doc-1", "科技", db_path=db_path)

    assert sqlite_store.get_document("doc-1", db_path=db_path).category == "科技"


def test_bulk_update_category_returns_affected_row_count(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    sqlite_store.insert_document(
        Document(id="doc-a", source_path="/tmp/a.md", title="A", content="a"), [], db_path=db_path
    )
    sqlite_store.insert_document(
        Document(id="doc-b", source_path="/tmp/b.md", title="B", content="b"), [], db_path=db_path
    )

    updated_count = sqlite_store.bulk_update_category(["doc-a", "doc-b", "doc-missing"], "新聞", db_path=db_path)

    assert updated_count == 2
    assert sqlite_store.get_document("doc-a", db_path=db_path).category == "新聞"
    assert sqlite_store.get_document("doc-b", db_path=db_path).category == "新聞"


def test_bulk_update_category_returns_zero_for_empty_id_list(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"

    assert sqlite_store.bulk_update_category([], "新聞", db_path=db_path) == 0


def test_list_documents_reports_has_translation(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    translated = Document(
        id="doc-a", source_path="/tmp/a.md", title="A", content="a", translated_content="甲"
    )
    untranslated = Document(id="doc-b", source_path="/tmp/b.md", title="B", content="b")
    sqlite_store.insert_document(translated, [], db_path=db_path)
    sqlite_store.insert_document(untranslated, [], db_path=db_path)

    summaries = {s.id: s for s in sqlite_store.list_documents(db_path=db_path)}

    assert summaries["doc-a"].has_translation is True
    assert summaries["doc-b"].has_translation is False


def test_list_documents_missing_translation_returns_only_untranslated(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    translated = Document(
        id="doc-a", source_path="/tmp/a.md", title="A", content="a", translated_content="甲"
    )
    untranslated = Document(id="doc-b", source_path="/tmp/b.md", title="B", content="b")
    sqlite_store.insert_document(translated, [], db_path=db_path)
    sqlite_store.insert_document(untranslated, [], db_path=db_path)

    pending = sqlite_store.list_documents_missing_translation(db_path=db_path)

    assert [d.id for d in pending] == ["doc-b"]


def test_update_translated_content(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    sqlite_store.insert_document(document, [], db_path=db_path)

    sqlite_store.update_translated_content("doc-1", "你好", db_path=db_path)

    fetched = sqlite_store.get_document("doc-1", db_path=db_path)
    assert fetched.translated_content == "你好"


def test_insert_feed_subscription_round_trips(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    feed = FeedSubscription(id="feed-1", url="https://example.com/rss.xml", name="Example Feed", category="財經")

    sqlite_store.insert_feed_subscription(feed, db_path=db_path)
    fetched = sqlite_store.get_feed_subscription_by_url("https://example.com/rss.xml", db_path=db_path)

    assert fetched is not None
    assert fetched.id == "feed-1"
    assert fetched.name == "Example Feed"
    assert fetched.last_synced_at is None
    assert fetched.category == "財經"


def test_update_feed_category_changes_existing_subscription(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    feed = FeedSubscription(id="feed-1", url="https://example.com/rss.xml", name="Example Feed")
    sqlite_store.insert_feed_subscription(feed, db_path=db_path)

    sqlite_store.update_feed_category("https://example.com/rss.xml", "科技", db_path=db_path)

    fetched = sqlite_store.get_feed_subscription_by_url("https://example.com/rss.xml", db_path=db_path)
    assert fetched.category == "科技"


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
