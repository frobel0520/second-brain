from pathlib import Path
from types import SimpleNamespace

import pytest

from second_brain.models import Document
from second_brain.processing import embedding as embedding_module
from second_brain.processing.chunking import chunk_document
from second_brain.processing.embedding import EmbeddingProvider
from second_brain.retrieval import ask as ask_module
from second_brain.storage import sqlite_store, store, vector_store


class _FakeEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class _FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


class _FakeAnthropicClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessages(text)


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(vector_store, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", _FakeEmbeddingProvider())
    yield
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(embedding_module, "_default_provider", None)


def test_ask_returns_placeholder_when_nothing_stored() -> None:
    result = ask_module.ask("有什麼筆記?")

    assert result.answer == "知識庫裡目前沒有相關的筆記可以回答這個問題。"
    assert result.sources == []


def test_ask_builds_context_and_returns_model_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    document = Document(id="doc-1", source_path="/tmp/note.md", title="測試筆記", content="這是測試內容。")
    chunks = chunk_document(document)
    provider = embedding_module.get_embedding_provider()
    embeddings = provider.embed([chunk.content for chunk in chunks])
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb
    store.save_document(document, chunks)

    monkeypatch.setattr(ask_module.anthropic, "Anthropic", lambda: _FakeAnthropicClient("這是回答。"))

    result = ask_module.ask("測試問題")

    assert result.answer == "這是回答。"
    assert len(result.sources) == 1
    assert result.sources[0].document.id == "doc-1"
