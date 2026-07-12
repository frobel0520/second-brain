"""文字前處理共用工具:中英文斷詞,自動標籤跟關鍵字搜尋共用同一套邏輯。"""

from __future__ import annotations

import re

import jieba

# 中英文常見的虛詞/停用詞,斷詞後濾掉,不然標籤/關鍵字搜尋都會被這些字洗版。
STOPWORDS = {
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


def tokenize(text: str) -> list[str]:
    """中文用 jieba 斷詞(本機執行,免 API key、不用連網),英文單字原樣保留,濾掉停用詞。"""
    tokens = (token.strip().lower() for token in jieba.cut(text))
    return [
        token
        for token in tokens
        if len(token) >= 2 and _MEANINGFUL_TOKEN.search(token) and token not in STOPWORDS
    ]
