from pathlib import Path

import pytest

from second_brain.models import Document
from second_brain.processing import embedding as embedding_module
from second_brain.processing.chunking import chunk_document
from second_brain.processing.embedding import EmbeddingProvider
from second_brain.retrieval.search import search
from second_brain.storage import sqlite_store, store, vector_store


class _FakeEmbeddingProvider(EmbeddingProvider):
    """回傳可預期的固定向量,測試不需要載入真的模型。"""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "貓" in text else [0.0, 1.0] for text in texts]


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", _FakeEmbeddingProvider())
    yield
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", None)


def _add(document: Document) -> None:
    chunks = chunk_document(document)
    provider = embedding_module.get_embedding_provider()
    embeddings = provider.embed([chunk.content for chunk in chunks])
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb
    store.save_document(document, chunks)


def test_search_ranks_most_similar_document_first() -> None:
    cat_doc = Document(id="doc-cat", source_path="/tmp/cat.md", title="貓咪筆記", content="這是一篇關於貓的筆記。")
    dog_doc = Document(id="doc-dog", source_path="/tmp/dog.md", title="狗狗筆記", content="這是一篇關於狗的筆記。")
    _add(cat_doc)
    _add(dog_doc)

    results = search("貓在哪裡", top_k=1)

    assert len(results) == 1
    assert results[0].document.id == "doc-cat"
    assert results[0].document.title == "貓咪筆記"


def test_search_returns_empty_list_when_nothing_stored() -> None:
    assert search("隨便問問") == []


def test_search_ranks_exact_keyword_match_first_when_semantic_scores_tie() -> None:
    """三篇文章都不含「貓」,fake embedding 給的向量會一樣、語意分數打平,
    這時候排名應該由 BM25 關鍵字分數決定——這是 hybrid search 真正要解決的
    情境(精確詞彙搜尋,例如套件名稱)。用三篇(不是兩篇)是因為 BM25 的 idf
    在 corpus 只有兩篇文件時,一個詞只出現在其中一篇的 idf 剛好算出 0,會讓
    這個測試在沒有真的排序邏輯的情況下也「碰巧」通過。"""
    keyword_doc = Document(
        id="doc-keyword",
        source_path="/tmp/sqlite-utils.md",
        title="套件更新",
        content="sqlite-utils 套件更新了新版本,加了很多功能。",
    )
    unrelated_doc_1 = Document(
        id="doc-unrelated-1",
        source_path="/tmp/weather.md",
        title="天氣",
        content="這是一篇跟資料庫工具完全無關的筆記,純粹講今天天氣。",
    )
    unrelated_doc_2 = Document(
        id="doc-unrelated-2",
        source_path="/tmp/travel.md",
        title="旅遊",
        content="這是一篇跟資料庫工具完全無關的筆記,純粹講出國旅遊。",
    )
    _add(keyword_doc)
    _add(unrelated_doc_1)
    _add(unrelated_doc_2)

    results = search("sqlite-utils", top_k=3)

    assert results[0].document.id == "doc-keyword"


def test_search_filters_by_category() -> None:
    cat_doc = Document(
        id="doc-cat", source_path="/tmp/cat.md", title="貓咪筆記", content="這是一篇關於貓的筆記。", category="新聞"
    )
    cat_doc_tech = Document(
        id="doc-cat-tech",
        source_path="/tmp/cat-tech.md",
        title="貓咪科技筆記",
        content="這是另一篇關於貓的筆記。",
        category="科技",
    )
    _add(cat_doc)
    _add(cat_doc_tech)

    results = search("貓在哪裡", top_k=5, category="新聞")

    assert [result.document.id for result in results] == ["doc-cat"]


def test_search_returns_empty_list_when_category_has_no_documents() -> None:
    _add(Document(id="doc-cat", source_path="/tmp/cat.md", title="貓咪筆記", content="這是一篇關於貓的筆記。", category="新聞"))

    assert search("貓在哪裡", category="財經") == []
