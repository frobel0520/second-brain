"""SQLite 讀寫封裝:存 metadata、原文、來源資訊。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from second_brain.config import SQLITE_PATH, ensure_data_dir
from second_brain.models import Chunk, Document, DocumentSummary, FeedSubscription

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    translated_content TEXT,
    category TEXT,
    starred INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feeds (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    added_at TEXT NOT NULL,
    last_synced_at TEXT,
    category TEXT
);
"""


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(db_path or SQLITE_PATH)
    conn.executescript(_SCHEMA)
    _ensure_column(conn, "documents", "translated_content", "translated_content TEXT")
    _ensure_column(conn, "documents", "category", "category TEXT")
    _ensure_column(conn, "documents", "starred", "starred INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "feeds", "category", "category TEXT")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """幫既有(在這欄位存在之前建立的)資料庫補上欄位。

    `CREATE TABLE IF NOT EXISTS` 不會幫已經存在的資料表補欄位,SQLite 也沒有
    `ADD COLUMN IF NOT EXISTS`,所以用 `PRAGMA table_info` 自己檢查。
    """
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def insert_document(document: Document, chunks: list[Chunk], db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO documents "
                "(id, source_path, title, content, created_at, metadata, tags, translated_content, category, starred) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    document.id,
                    document.source_path,
                    document.title,
                    document.content,
                    document.created_at.isoformat(),
                    json.dumps(document.metadata, ensure_ascii=False),
                    json.dumps(document.tags, ensure_ascii=False),
                    document.translated_content,
                    document.category,
                    int(document.starred),
                ),
            )
            conn.executemany(
                "INSERT INTO chunks (id, document_id, chunk_index, content, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.chunk_index,
                        chunk.content,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                    for chunk in chunks
                ],
            )
    finally:
        conn.close()


def _row_to_document(row: tuple) -> Document:
    doc_id, source_path, title, content, created_at, metadata, tags, translated_content, category, starred = row
    return Document(
        id=doc_id,
        source_path=source_path,
        title=title,
        content=content,
        created_at=datetime.fromisoformat(created_at),
        metadata=json.loads(metadata),
        tags=json.loads(tags),
        translated_content=translated_content,
        category=category,
        starred=bool(starred),
    )


_DOCUMENT_COLUMNS = (
    "id, source_path, title, content, created_at, metadata, tags, translated_content, category, starred"
)


def get_document(document_id: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_document(row)


def get_document_by_source_path(source_path: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE source_path = ?",
            (source_path,),
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_document(row)


def get_document_by_content(content: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE content = ?",
            (content,),
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_document(row)


def list_documents(db_path: Path | None = None) -> list[DocumentSummary]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.id, d.title, d.source_path, d.created_at, d.tags, COUNT(c.id), "
            "d.translated_content IS NOT NULL, d.category, d.starred "
            "FROM documents d LEFT JOIN chunks c ON c.document_id = d.id "
            "GROUP BY d.id ORDER BY d.created_at"
        ).fetchall()
    finally:
        conn.close()

    return [
        DocumentSummary(
            id=row[0],
            title=row[1],
            source_path=row[2],
            created_at=datetime.fromisoformat(row[3]),
            tags=json.loads(row[4]),
            chunk_count=row[5],
            has_translation=bool(row[6]),
            category=row[7],
            starred=bool(row[8]),
        )
        for row in rows
    ]


def list_categories(db_path: Path | None = None) -> list[str]:
    """撈出目前知識庫裡用過的所有分類(去重、不含未分類),給 UI 當篩選/建議選項用。"""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM documents WHERE category IS NOT NULL ORDER BY category"
        ).fetchall()
    finally:
        conn.close()

    return [row[0] for row in rows]


def update_document_category(document_id: str, category: str | None, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("UPDATE documents SET category = ? WHERE id = ?", (category, document_id))
    finally:
        conn.close()


def set_document_starred(document_id: str, starred: bool, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("UPDATE documents SET starred = ? WHERE id = ?", (int(starred), document_id))
    finally:
        conn.close()


def bulk_update_category(document_ids: list[str], category: str, db_path: Path | None = None) -> int:
    """把一批文件的分類都設成同一個值,回傳實際更新的筆數。"""
    if not document_ids:
        return 0

    conn = _connect(db_path)
    try:
        with conn:
            placeholders = ", ".join("?" for _ in document_ids)
            cursor = conn.execute(
                f"UPDATE documents SET category = ? WHERE id IN ({placeholders})",
                [category, *document_ids],
            )
            return cursor.rowcount
    finally:
        conn.close()


def list_all_chunks(db_path: Path | None = None) -> list[Chunk]:
    """撈出知識庫裡全部的 chunk(不含 embedding),給 BM25 關鍵字搜尋當語料用。"""
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT id, document_id, chunk_index, content FROM chunks").fetchall()
    finally:
        conn.close()

    return [
        Chunk(id=row[0], document_id=row[1], chunk_index=row[2], content=row[3]) for row in rows
    ]


def get_chunk_ids(document_id: str, db_path: Path | None = None) -> list[str]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
        ).fetchall()
    finally:
        conn.close()

    return [row[0] for row in rows]


def delete_document(document_id: str, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    finally:
        conn.close()


def list_documents_missing_translation(db_path: Path | None = None) -> list[Document]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM documents "
            "WHERE translated_content IS NULL ORDER BY created_at"
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_document(row) for row in rows]


def update_translated_content(document_id: str, translated_content: str, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE documents SET translated_content = ? WHERE id = ?",
                (translated_content, document_id),
            )
    finally:
        conn.close()


def delete_all_documents(db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM documents")
    finally:
        conn.close()


def find_documents(
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    keyword: str | None = None,
    source: str | None = None,
    category: str | None = None,
    starred: bool | None = None,
    db_path: Path | None = None,
) -> list[DocumentSummary]:
    """依日期範圍、關鍵字、來源、分類、加星狀態找文件。

    日期/關鍵字/來源這三種是「符合任一個就算」(OR),不是同時符合;日期範圍
    (`created_after`/`created_before`)算一組,兩個都給的話彼此是 AND(定義一段
    區間),這段區間再跟關鍵字/來源用 OR 組合。`category`/`starred` 是獨立的
    AND 條件,疊加在前面那組 OR 結果之上(例如「分類是財經,而且標題含某關鍵字」;
    或「未加星,而且是七天前加入的」,用於批次清理)。沒給任何條件(含
    category/starred)會回傳空 list,呼叫端應該視為「至少要給一個條件」的
    錯誤,不要當成「符合全部」處理。
    """
    or_conditions: list[str] = []
    params: list[str] = []

    if created_after is not None or created_before is not None:
        date_parts = []
        if created_after is not None:
            date_parts.append("d.created_at >= ?")
            params.append(created_after.isoformat())
        if created_before is not None:
            date_parts.append("d.created_at <= ?")
            params.append(created_before.isoformat())
        or_conditions.append("(" + " AND ".join(date_parts) + ")")

    if keyword is not None:
        like = f"%{keyword}%"
        or_conditions.append("(d.title LIKE ? OR d.content LIKE ? OR d.tags LIKE ?)")
        params.extend([like, like, like])

    if source is not None:
        or_conditions.append("d.source_path LIKE ?")
        params.append(f"%{source}%")

    where_parts: list[str] = []
    if or_conditions:
        where_parts.append("(" + " OR ".join(or_conditions) + ")")
    elif category is None and starred is None:
        return []

    if category is not None:
        where_parts.append("d.category = ?")
        params.append(category)

    if starred is not None:
        where_parts.append("d.starred = ?")
        params.append(int(starred))

    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.id, d.title, d.source_path, d.created_at, d.tags, COUNT(c.id), d.category, "
            "d.translated_content IS NOT NULL, d.starred "
            "FROM documents d LEFT JOIN chunks c ON c.document_id = d.id "
            f"WHERE {' AND '.join(where_parts)} "
            "GROUP BY d.id ORDER BY d.created_at",
            params,
        ).fetchall()
    finally:
        conn.close()

    return [
        DocumentSummary(
            id=row[0],
            title=row[1],
            source_path=row[2],
            created_at=datetime.fromisoformat(row[3]),
            tags=json.loads(row[4]),
            chunk_count=row[5],
            category=row[6],
            has_translation=bool(row[7]),
            starred=bool(row[8]),
        )
        for row in rows
    ]


_FEED_COLUMNS = "id, url, name, added_at, last_synced_at, category"


def _row_to_feed_subscription(row: tuple) -> FeedSubscription:
    feed_id, url, name, added_at, last_synced_at, category = row
    return FeedSubscription(
        id=feed_id,
        url=url,
        name=name,
        added_at=datetime.fromisoformat(added_at),
        last_synced_at=datetime.fromisoformat(last_synced_at) if last_synced_at else None,
        category=category,
    )


def insert_feed_subscription(feed: FeedSubscription, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO feeds (id, url, name, added_at, last_synced_at, category) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    feed.id,
                    feed.url,
                    feed.name,
                    feed.added_at.isoformat(),
                    feed.last_synced_at.isoformat() if feed.last_synced_at else None,
                    feed.category,
                ),
            )
    finally:
        conn.close()


def get_feed_subscription_by_url(url: str, db_path: Path | None = None) -> FeedSubscription | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            f"SELECT {_FEED_COLUMNS} FROM feeds WHERE url = ?", (url,)
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_feed_subscription(row)


def list_feed_subscriptions(db_path: Path | None = None) -> list[FeedSubscription]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(f"SELECT {_FEED_COLUMNS} FROM feeds ORDER BY added_at").fetchall()
    finally:
        conn.close()

    return [_row_to_feed_subscription(row) for row in rows]


def update_feed_category(url: str, category: str | None, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("UPDATE feeds SET category = ? WHERE url = ?", (category, url))
    finally:
        conn.close()


def update_feed_last_synced(url: str, synced_at: datetime, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("UPDATE feeds SET last_synced_at = ? WHERE url = ?", (synced_at.isoformat(), url))
    finally:
        conn.close()


def delete_feed_subscription(url: str, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM feeds WHERE url = ?", (url,))
    finally:
        conn.close()
