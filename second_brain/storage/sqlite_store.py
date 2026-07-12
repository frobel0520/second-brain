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
    tags TEXT NOT NULL DEFAULT '[]'
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
    last_synced_at TEXT
);
"""


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(db_path or SQLITE_PATH)
    conn.executescript(_SCHEMA)
    return conn


def insert_document(document: Document, chunks: list[Chunk], db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO documents (id, source_path, title, content, created_at, metadata, tags) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    document.id,
                    document.source_path,
                    document.title,
                    document.content,
                    document.created_at.isoformat(),
                    json.dumps(document.metadata, ensure_ascii=False),
                    json.dumps(document.tags, ensure_ascii=False),
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
    doc_id, source_path, title, content, created_at, metadata, tags = row
    return Document(
        id=doc_id,
        source_path=source_path,
        title=title,
        content=content,
        created_at=datetime.fromisoformat(created_at),
        metadata=json.loads(metadata),
        tags=json.loads(tags),
    )


def get_document(document_id: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, source_path, title, content, created_at, metadata, tags FROM documents "
            "WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_document(row)


def get_document_by_source_path(source_path: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, source_path, title, content, created_at, metadata, tags FROM documents "
            "WHERE source_path = ?",
            (source_path,),
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_document(row)


def get_document_by_content(content: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, source_path, title, content, created_at, metadata, tags FROM documents "
            "WHERE content = ?",
            (content,),
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_document(row)


def list_documents(db_path: Path | None = None) -> list[DocumentSummary]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.id, d.title, d.source_path, d.created_at, d.tags, COUNT(c.id) "
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
        )
        for row in rows
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
    db_path: Path | None = None,
) -> list[DocumentSummary]:
    """依日期範圍、關鍵字、來源找文件,三種條件是「符合任一個就算」(OR),不是同時符合。

    日期範圍(`created_after`/`created_before`)算一組:兩個都給的話彼此是 AND
    (定義一段區間),這段區間再跟關鍵字/來源用 OR 組合。沒給任何條件會回傳空
    list,呼叫端應該視為「至少要給一個條件」的錯誤,不要當成「符合全部」處理。
    """
    conditions: list[str] = []
    params: list[str] = []

    if created_after is not None or created_before is not None:
        date_parts = []
        if created_after is not None:
            date_parts.append("d.created_at >= ?")
            params.append(created_after.isoformat())
        if created_before is not None:
            date_parts.append("d.created_at <= ?")
            params.append(created_before.isoformat())
        conditions.append("(" + " AND ".join(date_parts) + ")")

    if keyword is not None:
        like = f"%{keyword}%"
        conditions.append("(d.title LIKE ? OR d.content LIKE ? OR d.tags LIKE ?)")
        params.extend([like, like, like])

    if source is not None:
        conditions.append("d.source_path LIKE ?")
        params.append(f"%{source}%")

    if not conditions:
        return []

    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.id, d.title, d.source_path, d.created_at, d.tags, COUNT(c.id) "
            "FROM documents d LEFT JOIN chunks c ON c.document_id = d.id "
            f"WHERE {' OR '.join(conditions)} "
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
        )
        for row in rows
    ]


def _row_to_feed_subscription(row: tuple) -> FeedSubscription:
    feed_id, url, name, added_at, last_synced_at = row
    return FeedSubscription(
        id=feed_id,
        url=url,
        name=name,
        added_at=datetime.fromisoformat(added_at),
        last_synced_at=datetime.fromisoformat(last_synced_at) if last_synced_at else None,
    )


def insert_feed_subscription(feed: FeedSubscription, db_path: Path | None = None) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO feeds (id, url, name, added_at, last_synced_at) VALUES (?, ?, ?, ?, ?)",
                (
                    feed.id,
                    feed.url,
                    feed.name,
                    feed.added_at.isoformat(),
                    feed.last_synced_at.isoformat() if feed.last_synced_at else None,
                ),
            )
    finally:
        conn.close()


def get_feed_subscription_by_url(url: str, db_path: Path | None = None) -> FeedSubscription | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, url, name, added_at, last_synced_at FROM feeds WHERE url = ?", (url,)
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_feed_subscription(row)


def list_feed_subscriptions(db_path: Path | None = None) -> list[FeedSubscription]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, url, name, added_at, last_synced_at FROM feeds ORDER BY added_at"
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_feed_subscription(row) for row in rows]


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
