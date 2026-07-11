"""ChromaDB 讀寫封裝(persistent client,純本機檔案,不開伺服器)。"""

from __future__ import annotations

from second_brain.config import CHROMA_DIR, ensure_data_dir
from second_brain.models import Chunk

_COLLECTION_NAME = "chunks"

_client = None


def _get_collection():
    global _client
    if _client is None:
        import chromadb

        ensure_data_dir()
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client.get_or_create_collection(_COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def add_chunks(chunks: list[Chunk]) -> None:
    if not chunks:
        return

    missing = [c.id for c in chunks if c.embedding is None]
    if missing:
        raise ValueError(f"以下 chunk 尚未產生 embedding: {missing}")

    collection = _get_collection()
    collection.add(
        ids=[c.id for c in chunks],
        embeddings=[c.embedding for c in chunks],
        documents=[c.content for c in chunks],
        metadatas=[
            {"document_id": c.document_id, "chunk_index": c.chunk_index} for c in chunks
        ],
    )


def query_similar(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    collection = _get_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
    )

    return [
        {
            "chunk_id": chunk_id,
            "document_id": metadata["document_id"],
            "chunk_index": metadata["chunk_index"],
            "content": content,
            "distance": distance,
        }
        for chunk_id, content, metadata, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]
