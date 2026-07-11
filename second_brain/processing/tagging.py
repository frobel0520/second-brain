"""自動標籤介面。包一層抽象,方便之後從關鍵字抽取換成 LLM 或其他分類邏輯。"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter

from second_brain.config import MAX_TAGS
from second_brain.models import Document

# 中英文常見的虛詞/停用詞,詞頻抽取時先濾掉,不然標籤會被這些字洗版。
_STOPWORDS = {
    "的", "了", "是", "在", "和", "與", "也", "都", "就", "而", "或", "及",
    "之", "其", "這", "那", "你", "我", "他", "她", "它", "我們", "你們",
    "他們", "這個", "那個", "一個", "沒有", "可以", "需要", "因為", "所以",
    "但是", "如果", "這樣", "那樣", "什麼", "怎麼", "為什麼", "不會", "不是",
    "已經", "還是", "還有", "這些", "那些", "一些", "自己", "現在", "時候",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "of", "to", "in", "on", "at", "for", "with", "by", "from", "as", "it",
    "this", "that", "these", "those", "and", "or", "but", "if", "then",
    "than", "so", "not", "no", "yes", "you", "your", "we", "our", "they",
    "their", "he", "she", "i", "my",
}

# 只留下「至少含一個中文字或英文字母」的詞,濾掉標點/數字/空白等斷詞雜訊。
_MEANINGFUL_TOKEN = re.compile(r"[一-鿿A-Za-z]")


def _tokenize(text: str) -> list[str]:
    """中文用 jieba 斷詞(本機執行,免 API key、不用連網),英文單字原樣保留。"""
    import jieba

    tokens = (token.strip().lower() for token in jieba.cut(text))
    return [token for token in tokens if len(token) >= 2 and _MEANINGFUL_TOKEN.search(token)]


class TaggingProvider(ABC):
    @abstractmethod
    def tag(self, document: Document) -> list[str]:
        """幫一份文件產生標籤,依重要性排序回傳(最重要的在前面)。"""


class KeywordFrequencyTaggingProvider(TaggingProvider):
    """本機執行、免 API key 的預設 provider:用詞頻抽取最常出現的關鍵字當標籤。"""

    def __init__(self, max_tags: int = MAX_TAGS) -> None:
        self._max_tags = max_tags

    def tag(self, document: Document) -> list[str]:
        tokens = [token for token in _tokenize(document.content) if token not in _STOPWORDS]
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
