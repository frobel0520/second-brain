"""Embedding 介面。包一層抽象,方便之後從 sentence-transformers 換成別的模型或 API。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from second_brain.config import EMBEDDING_MODEL_NAME


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """把一批文字轉成向量,回傳順序與輸入一致。"""


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """本機執行、離線可用、免 API key 的預設 provider。"""

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME) -> None:
        self._model_name = model_name
        self._model = None  # 延遲載入,避免 import 就觸發下載/讀模型

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._get_model().encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


_default_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = SentenceTransformerEmbeddingProvider()
    return _default_provider
