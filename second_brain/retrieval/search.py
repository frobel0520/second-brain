"""語意搜尋:把 query 轉成向量,再到向量庫裡找最相似的片段。"""

from __future__ import annotations

from second_brain.models import SearchResult
from second_brain.processing.embedding import get_embedding_provider
from second_brain.storage import search_similar


def search(query: str, top_k: int = 5) -> list[SearchResult]:
    provider = get_embedding_provider()
    [query_embedding] = provider.embed([query])
    return search_similar(query_embedding, top_k=top_k)
