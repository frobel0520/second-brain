"""對外的乾淨介面。上層不應該直接碰 SQLite/ChromaDB 的細節,只透過這裡互動。"""

from __future__ import annotations

from second_brain.models import Chunk, Document, DocumentSummary, SearchResult
from second_brain.storage import sqlite_store, vector_store


def save_document(document: Document, chunks: list[Chunk]) -> None:
    sqlite_store.insert_document(document, chunks)
    vector_store.add_chunks(chunks)


def list_documents() -> list[DocumentSummary]:
    return sqlite_store.list_documents()


def _delete_by_source_path(source_path: str) -> str | None:
    existing = sqlite_store.get_document_by_source_path(source_path)
    if existing is None:
        return None

    chunk_ids = sqlite_store.get_chunk_ids(existing.id)
    vector_store.delete_chunks(chunk_ids)
    sqlite_store.delete_document(existing.id)
    return existing.title


def replace_existing_document(source_path: str) -> str | None:
    """若同一個來源檔案已經存在,先刪除舊版本(sqlite + chroma)。

    回傳被取代的文件標題;沒有舊版本就回傳 None。
    """
    return _delete_by_source_path(source_path)


def remove_document(source_path: str) -> str | None:
    """從知識庫刪除指定來源檔案的文件(sqlite + chroma)。

    回傳被刪除的文件標題;找不到就回傳 None。
    """
    return _delete_by_source_path(source_path)


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
