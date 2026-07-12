"""混合搜尋:語意向量相似度 + BM25 關鍵字搜尋,正規化後加權合併。

語意搜尋對「概念相關」的查詢準,但對精確詞彙(人名、版本號、套件名稱)容易
抓不準;關鍵字搜尋反過來對這類精確詞彙準,但抓不到用詞不同卻語意相關的
內容。兩者一起跑、各自正規化到 0~1 後加權平均,截長補短。
"""

from __future__ import annotations

from second_brain.config import KEYWORD_WEIGHT, SEMANTIC_WEIGHT
from second_brain.models import SearchResult
from second_brain.processing.embedding import get_embedding_provider
from second_brain.retrieval.keyword_search import keyword_scores
from second_brain.storage import search_similar

# 知識庫目前的規模(幾十篇文章、至多幾百個 chunk)全部撈出來對排名沒有影響,
# 用一個夠大的數字把所有 chunk 的語意分數都拿到,才能跟關鍵字分數對齊做正規化。
_ALL_CHUNKS_TOP_K = 10_000


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}

    values = scores.values()
    lo, hi = min(values), max(values)
    if hi == lo:
        return {chunk_id: 1.0 for chunk_id in scores}
    return {chunk_id: (value - lo) / (hi - lo) for chunk_id, value in scores.items()}


def search(query: str, top_k: int = 5) -> list[SearchResult]:
    provider = get_embedding_provider()
    [query_embedding] = provider.embed([query])
    all_semantic = search_similar(query_embedding, top_k=_ALL_CHUNKS_TOP_K)
    if not all_semantic:
        return []

    semantic_scores = {result.chunk.id: result.score for result in all_semantic}
    normalized_semantic = _normalize(semantic_scores)
    normalized_keyword = _normalize(keyword_scores(query))

    combined_scores = {
        chunk_id: SEMANTIC_WEIGHT * normalized_semantic.get(chunk_id, 0.0)
        + KEYWORD_WEIGHT * normalized_keyword.get(chunk_id, 0.0)
        for chunk_id in semantic_scores
    }

    ranked = sorted(all_semantic, key=lambda result: combined_scores[result.chunk.id], reverse=True)
    for result in ranked:
        result.score = combined_scores[result.chunk.id]

    return ranked[:top_k]
