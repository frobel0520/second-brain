from pathlib import Path

import pytest

from second_brain.models import Chunk, Document
from second_brain.retrieval.keyword_search import keyword_scores
from second_brain.storage import sqlite_store, store, vector_store


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)
    yield
    monkeypatch.setattr(vector_store, "_client", None)


def _save(doc_id: str, source_path: str, title: str, content: str) -> None:
    document = Document(id=doc_id, source_path=source_path, title=title, content=content)
    chunk = Chunk(id=f"{doc_id}-chunk", document_id=doc_id, content=content, chunk_index=0, embedding=[0.1, 0.2])
    store.save_document(document, [chunk])


def test_keyword_scores_returns_empty_dict_when_nothing_stored() -> None:
    assert keyword_scores("sqlite-utils") == {}


def test_keyword_scores_ranks_exact_term_match_higher() -> None:
    # 用三篇文件(不是兩篇)才能讓 BM25 的 idf 有意義——corpus 只有兩篇時,
    # 一個詞只出現在其中一篇的 idf 剛好算出 0(log(1.5/1.5)),會讓這個測試
    # 在沒有真的排序邏輯的情況下也「碰巧」通過。
    _save("doc-match", "/tmp/match.md", "套件更新", "sqlite-utils 套件更新了新版本,加了很多功能。")
    _save("doc-nomatch-1", "/tmp/nomatch1.md", "天氣", "這是一篇跟資料庫工具完全無關的筆記,純粹講今天天氣。")
    _save("doc-nomatch-2", "/tmp/nomatch2.md", "旅遊", "這是一篇跟資料庫工具完全無關的筆記,純粹講出國旅遊。")

    scores = keyword_scores("sqlite-utils")

    assert scores["doc-match-chunk"] > scores["doc-nomatch-1-chunk"]
    assert scores["doc-match-chunk"] > scores["doc-nomatch-2-chunk"]
