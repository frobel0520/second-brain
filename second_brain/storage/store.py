"""對外的乾淨介面。上層不應該直接碰 SQLite/ChromaDB 的細節,只透過這裡互動。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from second_brain.models import Chunk, Document, DocumentSummary, FeedSubscription, SearchResult
from second_brain.storage import sqlite_store, vector_store


def find_documents(
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    keyword: str | None = None,
    source: str | None = None,
    category: str | None = None,
) -> list[DocumentSummary]:
    return sqlite_store.find_documents(
        created_after=created_after,
        created_before=created_before,
        keyword=keyword,
        source=source,
        category=category,
    )


def list_categories() -> list[str]:
    return sqlite_store.list_categories()


def set_document_categories(document_ids: list[str], category: str) -> int:
    """把一批文件的分類都設成同一個值,回傳實際更新的筆數。"""
    return sqlite_store.bulk_update_category(document_ids, category)


def save_document(document: Document, chunks: list[Chunk]) -> None:
    sqlite_store.insert_document(document, chunks)
    vector_store.add_chunks(chunks)


def list_documents() -> list[DocumentSummary]:
    return sqlite_store.list_documents()


def list_all_chunks() -> list[Chunk]:
    return sqlite_store.list_all_chunks()


def get_document(document_id: str) -> Document | None:
    return sqlite_store.get_document(document_id)


def _delete_document(existing: Document) -> None:
    chunk_ids = sqlite_store.get_chunk_ids(existing.id)
    vector_store.delete_chunks(chunk_ids)
    sqlite_store.delete_document(existing.id)


def replace_existing_document(source_path: str, content: str) -> Document | None:
    """若同一份筆記已經存在,先刪除舊版本(sqlite + chroma)。

    比對邏輯:先看 source_path 有沒有舊紀錄(內容改了但路徑沒變);找不到
    再看有沒有 content 完全相同的舊紀錄(路徑變了但內容沒變 —— 例如檔案
    改名/搬家)。回傳被取代的舊版本 Document,呼叫端可以比較
    `existing.source_path` 跟新路徑是否不同來判斷是不是搬家;沒有舊版本
    就回傳 None。
    """
    existing = sqlite_store.get_document_by_source_path(source_path)
    if existing is None:
        existing = sqlite_store.get_document_by_content(content)
    if existing is None:
        return None

    _delete_document(existing)
    return existing


def remove_document(source_path: str) -> str | None:
    """從知識庫刪除指定來源檔案的文件(sqlite + chroma)。

    回傳被刪除的文件標題;找不到就回傳 None。
    """
    existing = sqlite_store.get_document_by_source_path(source_path)
    if existing is None:
        return None

    _delete_document(existing)
    return existing.title


def remove_documents(document_ids: list[str]) -> list[str]:
    """依 id 批次刪除文件(sqlite + chroma)。回傳實際被刪除的文件標題列表。"""
    removed_titles = []
    for document_id in document_ids:
        document = sqlite_store.get_document(document_id)
        if document is None:
            continue
        _delete_document(document)
        removed_titles.append(document.title)
    return removed_titles


def clear_all() -> int:
    """清空整個知識庫(sqlite + chroma)。回傳被清掉的文件數量。"""
    removed_count = len(sqlite_store.list_documents())
    sqlite_store.delete_all_documents()
    vector_store.delete_all_chunks()
    return removed_count


def search_similar(query_embedding: list[float], top_k: int = 5) -> list[SearchResult]:
    matches = vector_store.query_similar(query_embedding, top_k=top_k)

    document_cache: dict[str, Document] = {}
    results: list[SearchResult] = []

    for match in matches:
        document_id = match["document_id"]
        if document_id not in document_cache:
            document = sqlite_store.get_document(document_id)
            if document is None:
                continue
            document_cache[document_id] = document

        chunk = Chunk(
            id=match["chunk_id"],
            document_id=document_id,
            content=match["content"],
            chunk_index=match["chunk_index"],
        )
        results.append(
            SearchResult(
                chunk=chunk,
                document=document_cache[document_id],
                score=1 - match["distance"],
            )
        )

    return results


def subscribe_feed(url: str, name: str, category: str | None = None) -> FeedSubscription | None:
    """把一個 RSS/Atom 來源加進訂閱清單。同一個網址已經訂閱過就回傳 None。"""
    if sqlite_store.get_feed_subscription_by_url(url) is not None:
        return None

    feed = FeedSubscription(id=str(uuid.uuid4()), url=url, name=name, category=category)
    sqlite_store.insert_feed_subscription(feed)
    return feed


def update_feed_category(url: str, category: str | None) -> FeedSubscription | None:
    """更新一個已訂閱來源的分類,只影響之後同步進來的新文章,不會回頭改已經存在的文件。

    回傳更新後的訂閱紀錄;找不到這個網址就回傳 None。
    """
    existing = sqlite_store.get_feed_subscription_by_url(url)
    if existing is None:
        return None

    sqlite_store.update_feed_category(url, category)
    existing.category = category
    return existing


def list_feed_subscriptions() -> list[FeedSubscription]:
    return sqlite_store.list_feed_subscriptions()


def unsubscribe_feed(url: str) -> FeedSubscription | None:
    """取消訂閱指定網址,回傳被移除的訂閱紀錄;找不到就回傳 None。不影響已經 ingest 的文件。"""
    existing = sqlite_store.get_feed_subscription_by_url(url)
    if existing is None:
        return None

    sqlite_store.delete_feed_subscription(url)
    return existing


def mark_feed_synced(url: str) -> None:
    sqlite_store.update_feed_last_synced(url, datetime.now(timezone.utc))


def list_documents_missing_translation() -> list[Document]:
    return sqlite_store.list_documents_missing_translation()


def update_translated_content(document_id: str, translated_content: str) -> None:
    sqlite_store.update_translated_content(document_id, translated_content)
