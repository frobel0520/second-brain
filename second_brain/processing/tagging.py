"""自動標籤介面。包一層抽象,方便之後從關鍵字抽取換成 LLM 或其他分類邏輯。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter

from second_brain.config import MAX_TAGS
from second_brain.models import Document
from second_brain.processing.text import tokenize


class TaggingProvider(ABC):
    @abstractmethod
    def tag(self, document: Document) -> list[str]:
        """幫一份文件產生標籤,依重要性排序回傳(最重要的在前面)。"""


class KeywordFrequencyTaggingProvider(TaggingProvider):
    """本機執行、免 API key 的預設 provider:用詞頻抽取最常出現的關鍵字當標籤。"""

    def __init__(self, max_tags: int = MAX_TAGS) -> None:
        self._max_tags = max_tags

    def tag(self, document: Document) -> list[str]:
        tokens = tokenize(document.content)
        if not tokens:
            return []

        counts = Counter(tokens)
        return [word for word, _ in counts.most_common(self._max_tags)]


_default_provider: TaggingProvider | None = None


def get_tagging_provider() -> TaggingProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = KeywordFrequencyTaggingProvider()
    return _default_provider
