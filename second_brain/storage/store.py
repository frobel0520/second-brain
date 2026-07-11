"""對外的乾淨介面。上層不應該直接碰 SQLite/ChromaDB 的細節,只透過這裡互動。"""

from __future__ import annotations

from second_brain.models import Chunk, Document, DocumentSummary, SearchResult
from second_brain.storage import sqlite_store, vector_store


def save_document(document: Document, chunks: list[Chunk]) -> None:
    sqlite_store.insert_document(document, chunks)
    vector_store.add_chunks(chunks)


def list_documents() -> list[DocumentSummary]:
    return sqlite_store.list_documents()


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
