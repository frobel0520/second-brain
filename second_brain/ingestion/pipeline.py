"""把一份 Document 跑完標籤、切塊、embedding、dedupe、存檔的完整流程。

放在這裡而不是 interface/ 底下,是因為 CLI 跟 Streamlit 網頁介面都要共用
同一套邏輯,不應該讓兩個 interface 各自兜一份、各自處理 dedupe 訊息格式。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from second_brain.ingestion.rss_loader import load_feed
from second_brain.models import Document, FeedSubscription
from second_brain.processing.chunking import chunk_document
from second_brain.processing.embedding import get_embedding_provider
from second_brain.processing.tagging import get_tagging_provider
from second_brain.storage import (
    list_feed_subscriptions,
    mark_feed_synced,
    replace_existing_document,
    save_document,
)


@dataclass
class IngestResult:
    document: Document
    chunk_count: int
    status: Literal["added", "updated", "renamed"]
    previous_source_path: str | None = None


def ingest_document(document: Document) -> IngestResult | None:
    """標籤 → 切塊 → embedding → dedupe → 存檔。內容是空的就回傳 None,讓呼叫端決定怎麼處理。"""
    document.tags = get_tagging_provider().tag(document)
    chunks = chunk_document(document)

    if not chunks:
        return None

    replaced = replace_existing_document(document.source_path, document.content)

    provider = get_embedding_provider()
    embeddings = provider.embed([chunk.content for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    save_document(document, chunks)

    if replaced is None:
        status: Literal["added", "updated", "renamed"] = "added"
        previous_source_path = None
    elif replaced.source_path != document.source_path:
        status = "renamed"
        previous_source_path = replaced.source_path
    else:
        status = "updated"
        previous_source_path = None

    return IngestResult(
        document=document,
        chunk_count=len(chunks),
        status=status,
        previous_source_path=previous_source_path,
    )


@dataclass
class FeedSyncResult:
    feed: FeedSubscription
    added: int
    updated: int
    skipped: int
    error: str | None = None


def sync_feed_subscription(feed: FeedSubscription, limit: int | None = None) -> FeedSyncResult:
    """抓一個訂閱來源目前的文章,逐篇跑 `ingest_document()`,再更新 last_synced_at。

    抓取/解析失敗不會拋例外,包進 `FeedSyncResult.error` 讓呼叫端(CLI)自己決定
    要不要繼續處理其他訂閱來源——`sync_all_feed_subscriptions()` 就是靠這個
    設計,讓一個來源壞掉不會擋住其他來源的同步。
    """
    try:
        documents = load_feed(feed.url, limit=limit)
    except Exception as error:
        return FeedSyncResult(feed=feed, added=0, updated=0, skipped=0, error=str(error))

    added = updated = skipped = 0
    for document in documents:
        result = ingest_document(document)
        if result is None:
            skipped += 1
        elif result.status == "added":
            added += 1
        else:
            updated += 1

    mark_feed_synced(feed.url)
    return FeedSyncResult(feed=feed, added=added, updated=updated, skipped=skipped)


def sync_all_feed_subscriptions(limit: int | None = None) -> list[FeedSyncResult]:
    return [sync_feed_subscription(feed, limit=limit) for feed in list_feed_subscriptions()]
