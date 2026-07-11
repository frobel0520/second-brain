"""SQLite 讀寫封裝:存 metadata、原文、來源資訊。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from second_brain.config import SQLITE_PATH, ensure_data_dir
from second_brain.models import Chunk, Document, DocumentSummary

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL
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
                "INSERT INTO documents (id, source_path, title, content, created_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    document.id,
                    document.source_path,
                    document.title,
                    document.content,
                    document.created_at.isoformat(),
                    json.dumps(document.metadata),
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
                        json.dumps(chunk.metadata),
                    )
                    for chunk in chunks
                ],
            )
    finally:
        conn.close()


def _row_to_document(row: tuple) -> Document:
    doc_id, source_path, title, content, created_at, metadata = row
    return Document(
        id=doc_id,
        source_path=source_path,
        title=title,
        content=content,
        created_at=datetime.fromisoformat(created_at),
        metadata=json.loads(metadata),
    )


def get_document(document_id: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, source_path, title, content, created_at, metadata FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_document(row)


def get_document_by_source_path(source_path: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, source_path, title, content, created_at, metadata FROM documents "
            "WHERE source_path = ?",
            (source_path,),
        ).fetchone()
    finally:
        conn.close()

    return None if row is None else _row_to_document(row)


def list_documents(db_path: Path | None = None) -> list[DocumentSummary]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.id, d.title, d.source_path, d.created_at, COUNT(c.id) "
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
            chunk_count=row[4],
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
