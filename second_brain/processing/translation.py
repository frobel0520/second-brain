"""翻譯介面。包一層抽象,方便之後從 Anthropic API 換成別的翻譯模型或服務。

跟 embedding/tagging 不同,翻譯需要呼叫 Anthropic API,沒有免費、免 API key
的本機替代方案,所以這裡沒有預設的「本機 provider」——`ingest_document()`
呼叫翻譯失敗時會靜默跳過(不擋 ingestion),`second-brain translate` 這種
使用者主動觸發的指令則會把錯誤清楚回報出來,兩種錯誤處理方式在呼叫端,
不在這個模組裡。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import anthropic

from second_brain.config import ANSWER_MODEL

TRANSLATION_SYSTEM_PROMPT = (
    "你是專業譯者。把使用者提供的文字翻譯成繁體中文(台灣用語習慣),"
    "只回傳翻譯結果本身,不要加任何前言、說明或引號。"
    "如果原文已經是繁體中文,就照原樣回傳,不要做無意義的改寫。"
)


class TranslationProvider(ABC):
    @abstractmethod
    def translate(self, text: str) -> str:
        """把文字翻譯成繁體中文。"""


class AnthropicTranslationProvider(TranslationProvider):
    def translate(self, text: str) -> str:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=ANSWER_MODEL,
            max_tokens=4096,
            system=TRANSLATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


_default_provider: TranslationProvider | None = None


def get_translation_provider() -> TranslationProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = AnthropicTranslationProvider()
    return _default_provider
