"""BM25 關鍵字搜尋,用來補語意搜尋對精確詞彙(人名、版本號、專有名詞)抓不準的弱點。"""

from __future__ import annotations

from rank_bm25 import BM25Okapi

from second_brain.processing.text import tokenize
from second_brain.storage import list_all_chunks


def keyword_scores(query: str) -> dict[str, float]:
    """回傳每個 chunk id 對應的 BM25 分數(未正規化),語料是知識庫裡目前全部的 chunk。"""
    chunks = list_all_chunks()
    if not chunks:
        return {}

    corpus = [tokenize(chunk.content) for chunk in chunks]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(tokenize(query))

    return {chunk.id: score for chunk, score in zip(chunks, scores)}
