from pathlib import Path

import pytest

from second_brain.ingestion.pipeline import (
    ingest_document,
    sync_all_feed_subscriptions,
    sync_feed_subscription,
)
from second_brain.models import Document, FeedSubscription
from second_brain.processing import embedding as embedding_module
from second_brain.processing.embedding import EmbeddingProvider
from second_brain.storage import list_documents, sqlite_store, subscribe_feed, vector_store

_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>第一篇文章</title>
      <link>https://example.com/posts/1</link>
      <description>資料庫 索引 查詢內容。</description>
    </item>
    <item>
      <title>第二篇文章</title>
      <link>https://example.com/posts/2</link>
      <description>第二篇的內容。</description>
    </item>
  </channel>
</rss>
"""


class _FakeEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", _FakeEmbeddingProvider())
    yield
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", None)


def _document(source_path: str, title: str, content: str) -> Document:
    return Document(id=title, source_path=source_path, title=title, content=content)


def test_ingest_document_returns_none_for_empty_content() -> None:
    assert ingest_document(_document("/tmp/empty.md", "空的", "")) is None


def test_ingest_document_adds_new_document_and_generates_tags() -> None:
    result = ingest_document(_document("/tmp/note.md", "筆記", "database database index"))

    assert result is not None
    assert result.status == "added"
    assert result.chunk_count == 1
    assert result.previous_source_path is None
    assert "database" in result.document.tags
    assert len(list_documents()) == 1


def test_ingest_document_updates_when_same_path_reingested() -> None:
    ingest_document(_document("/tmp/note.md", "筆記", "第一版內容"))

    result = ingest_document(_document("/tmp/note.md", "筆記", "第二版內容"))

    assert result.status == "updated"
    assert result.previous_source_path is None
    assert len(list_documents()) == 1


def test_ingest_document_detects_rename_when_content_matches_different_path() -> None:
    ingest_document(_document("/old/note.md", "筆記", "相同內容"))

    result = ingest_document(_document("/new/note.md", "筆記", "相同內容"))

    assert result.status == "renamed"
    assert result.previous_source_path == "/old/note.md"
    assert len(list_documents()) == 1


def test_sync_feed_subscription_ingests_all_entries() -> None:
    feed = FeedSubscription(id="feed-1", url=_RSS_FEED, name="Test Feed")

    result = sync_feed_subscription(feed)

    assert result.error is None
    assert result.added == 2
    assert result.updated == 0
    assert result.skipped == 0
    assert len(list_documents()) == 2


def test_sync_feed_subscription_updates_last_synced_at() -> None:
    subscribe_feed(_RSS_FEED, "Test Feed")
    feed = sqlite_store.get_feed_subscription_by_url(_RSS_FEED)

    sync_feed_subscription(feed)

    refreshed = sqlite_store.get_feed_subscription_by_url(_RSS_FEED)
    assert refreshed.last_synced_at is not None


def test_sync_feed_subscription_reingesting_reports_updates() -> None:
    feed = FeedSubscription(id="feed-1", url=_RSS_FEED, name="Test Feed")
    sync_feed_subscription(feed)

    result = sync_feed_subscription(feed)

    assert result.added == 0
    assert result.updated == 2


def test_sync_feed_subscription_reports_error_without_raising() -> None:
    feed = FeedSubscription(id="feed-1", url="this is not a feed at all", name="Broken Feed")

    result = sync_feed_subscription(feed)

    assert result.error is not None
    assert result.added == 0


def test_sync_all_feed_subscriptions_syncs_every_subscription() -> None:
    subscribe_feed(_RSS_FEED, "Test Feed")

    results = sync_all_feed_subscriptions()

    assert len(results) == 1
    assert results[0].added == 2
