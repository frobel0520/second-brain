from pathlib import Path

from second_brain.models import Chunk, Document
from second_brain.storage import sqlite_store


def test_insert_document_persists_document_and_chunks(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello world")
    chunks = [
        Chunk(id="chunk-1", document_id="doc-1", content="hello", chunk_index=0),
        Chunk(id="chunk-2", document_id="doc-1", content="world", chunk_index=1),
    ]

    sqlite_store.insert_document(document, chunks, db_path=db_path)

    conn = sqlite_store._connect(db_path)
    try:
        doc_row = conn.execute("SELECT id, title FROM documents WHERE id = ?", (document.id,)).fetchone()
        chunk_rows = conn.execute(
            "SELECT id, chunk_index FROM chunks WHERE document_id = ? ORDER BY chunk_index", (document.id,)
        ).fetchall()
    finally:
        conn.close()

    assert doc_row == (document.id, document.title)
    assert chunk_rows == [("chunk-1", 0), ("chunk-2", 1)]


def test_get_document_returns_none_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"

    assert sqlite_store.get_document("nope", db_path=db_path) is None


def test_get_document_round_trips(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello world")
    sqlite_store.insert_document(document, [], db_path=db_path)

    fetched = sqlite_store.get_document("doc-1", db_path=db_path)

    assert fetched is not None
    assert fetched.id == document.id
    assert fetched.title == document.title
    assert fetched.content == document.content


def test_get_document_by_source_path(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    sqlite_store.insert_document(document, [], db_path=db_path)

    assert sqlite_store.get_document_by_source_path("/tmp/note.md", db_path=db_path).id == "doc-1"
    assert sqlite_store.get_document_by_source_path("/tmp/missing.md", db_path=db_path) is None


def test_list_documents_includes_chunk_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    doc_a = Document(id="doc-a", source_path="/tmp/a.md", title="A", content="a")
    doc_b = Document(id="doc-b", source_path="/tmp/b.md", title="B", content="b")
    sqlite_store.insert_document(
        doc_a, [Chunk(id="c1", document_id="doc-a", content="x", chunk_index=0)], db_path=db_path
    )
    sqlite_store.insert_document(doc_b, [], db_path=db_path)

    summaries = sqlite_store.list_documents(db_path=db_path)

    assert [s.id for s in summaries] == ["doc-a", "doc-b"]
    assert [s.chunk_count for s in summaries] == [1, 0]


def test_delete_document_removes_document_and_chunks(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    document = Document(id="doc-1", source_path="/tmp/note.md", title="note", content="hello")
    chunks = [Chunk(id="c1", document_id="doc-1", content="hello", chunk_index=0)]
    sqlite_store.insert_document(document, chunks, db_path=db_path)

    assert sqlite_store.get_chunk_ids("doc-1", db_path=db_path) == ["c1"]

    sqlite_store.delete_document("doc-1", db_path=db_path)

    assert sqlite_store.get_document("doc-1", db_path=db_path) is None
    assert sqlite_store.get_chunk_ids("doc-1", db_path=db_path) == []
