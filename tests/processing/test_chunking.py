from second_brain.models import Document
from second_brain.processing.chunking import chunk_document, chunk_text


def test_chunk_text_splits_with_overlap() -> None:
    text = "a" * 1000

    chunks = chunk_text(text, chunk_size=300, chunk_overlap=50)

    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)


def test_chunk_text_empty_input_returns_no_chunks() -> None:
    assert chunk_text("   ") == []


def test_chunk_document_assigns_sequential_indices() -> None:
    document = Document(
        id="doc-1",
        source_path="/tmp/note.md",
        title="note",
        content="x" * 500,
    )

    chunks = chunk_document(document, chunk_size=200, chunk_overlap=20)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.document_id == "doc-1" for c in chunks)
    assert all(c.embedding is None for c in chunks)
