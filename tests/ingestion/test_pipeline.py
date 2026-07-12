from pathlib import Path

import pytest

from second_brain.ingestion.pipeline import (
    ingest_document,
    sync_all_feed_subscriptions,
    sync_feed_subscription,
    translate_missing_documents,
)
from second_brain.models import Document, FeedSubscription
from second_brain.processing import embedding as embedding_module
from second_brain.processing import translation as translation_module
from second_brain.processing.embedding import EmbeddingProvider
from second_brain.processing.translation import TranslationProvider
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


class _FailingTranslationProvider(TranslationProvider):
    def translate(self, text: str) -> str:
        raise RuntimeError("translation service unavailable")


class _FakeTranslationProvider(TranslationProvider):
    def translate(self, text: str) -> str:
        return f"[translated] {text}"


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", _FakeEmbeddingProvider())
    monkeypatch.setattr(translation_module, "_default_provider", _FailingTranslationProvider())
    yield
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", None)
    monkeypatch.setattr(translation_module, "_default_provider", None)


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


def test_ingest_document_stamps_given_category() -> None:
    result = ingest_document(_document("/tmp/note.md", "筆記", "database index"), category="科技")

    assert result.document.category == "科技"


def test_ingest_document_defaults_to_no_category() -> None:
    result = ingest_document(_document("/tmp/note.md", "筆記", "database index"))

    assert result.document.category is None


def test_sync_feed_subscription_stamps_feed_category_on_every_document() -> None:
    feed = FeedSubscription(id="feed-1", url=_RSS_FEED, name="Test Feed", category="財經")

    sync_feed_subscription(feed)

    documents = list_documents()
    assert len(documents) == 2
    assert all(document.category == "財經" for document in documents)


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


def test_ingest_document_leaves_translated_content_none_when_translation_fails() -> None:
    """預設 fixture 用會失敗的 translation provider,模擬沒設 API key 的情況——
    翻譯失敗不該擋住 ingestion,只是 translated_content 留空。"""
    result = ingest_document(_document("/tmp/note.md", "筆記", "database database index"))

    assert result is not None
    assert result.translated is False
    assert result.document.translated_content is None


def test_ingest_document_sets_translated_content_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(translation_module, "_default_provider", _FakeTranslationProvider())

    result = ingest_document(_document("/tmp/note.md", "筆記", "hello world"))

    assert result.translated is True
    assert result.document.translated_content == "[translated] hello world"


def test_translate_missing_documents_translates_all_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    ingest_document(_document("/tmp/a.md", "A", "第一篇內容"))
    ingest_document(_document("/tmp/b.md", "B", "第二篇內容"))
    monkeypatch.setattr(translation_module, "_default_provider", _FakeTranslationProvider())

    result = translate_missing_documents()

    assert result.translated == 2
    assert result.failed == 0
    assert result.auth_error is None


def test_translate_missing_documents_skips_documents_that_already_have_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(translation_module, "_default_provider", _FakeTranslationProvider())
    ingest_document(_document("/tmp/a.md", "A", "第一篇內容"))

    result = translate_missing_documents()

    assert result.translated == 0
    assert result.failed == 0


def test_translate_missing_documents_stops_early_on_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _AuthFailingProvider(TranslationProvider):
        def translate(self, text: str) -> str:
            raise TypeError("Could not resolve authentication method")

    ingest_document(_document("/tmp/a.md", "A", "第一篇內容"))
    ingest_document(_document("/tmp/b.md", "B", "第二篇內容"))
    monkeypatch.setattr(translation_module, "_default_provider", _AuthFailingProvider())

    result = translate_missing_documents()

    assert result.auth_error is not None
    assert result.translated == 0


def test_translate_missing_documents_continues_after_non_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FlakyProvider(TranslationProvider):
        def __init__(self) -> None:
            self._calls = 0

        def translate(self, text: str) -> str:
            self._calls += 1
            if self._calls == 1:
                raise RuntimeError("temporary failure")
            return f"[translated] {text}"

    ingest_document(_document("/tmp/a.md", "A", "第一篇內容"))
    ingest_document(_document("/tmp/b.md", "B", "第二篇內容"))
    monkeypatch.setattr(translation_module, "_default_provider", _FlakyProvider())

    result = translate_missing_documents()

    assert result.translated == 1
    assert result.failed == 1
    assert result.auth_error is None
