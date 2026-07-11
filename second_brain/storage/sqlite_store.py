"""SQLite 讀寫封裝:存 metadata、原文、來源資訊。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from second_brain.config import SQLITE_PATH, ensure_data_dir
from second_brain.models import Chunk, Document

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


def get_document(document_id: str, db_path: Path | None = None) -> Document | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, source_path, title, content, created_at, metadata FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    doc_id, source_path, title, content, created_at, metadata = row
    return Document(
        id=doc_id,
        source_path=source_path,
        title=title,
        content=content,
        created_at=datetime.fromisoformat(created_at),
        metadata=json.loads(metadata),
    )
