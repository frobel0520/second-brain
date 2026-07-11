"""把 Document 切成適合 embedding 的 Chunk 片段。"""

from __future__ import annotations

import uuid

from second_brain.config import CHUNK_OVERLAP, CHUNK_SIZE
from second_brain.models import Chunk, Document


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    text = text.strip()
    if not text:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必須小於 chunk_size")

    chunks: list[str] = []
    start = 0
    step = chunk_size - chunk_overlap

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += step

    return [c for c in chunks if c]


def chunk_document(
    document: Document,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    texts = chunk_text(document.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    return [
        Chunk(
            id=str(uuid.uuid4()),
            document_id=document.id,
            content=text,
            chunk_index=index,
        )
        for index, text in enumerate(texts)
    ]
