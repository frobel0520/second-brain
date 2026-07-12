"""RAG 問答:在 search 結果基礎上,呼叫 Anthropic API 做問答總結。"""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

from second_brain.config import ANSWER_MODEL
from second_brain.models import SearchResult
from second_brain.retrieval.search import search

SYSTEM_PROMPT = (
    "你是一個個人知識庫的問答助理。"
    "只根據下面提供的筆記內容回答問題,不要使用筆記以外的知識。"
    "如果筆記內容不足以回答,請直接說明找不到相關資訊,不要編造。"
    "回答時盡量指出資訊來自哪一篇筆記。"
)


@dataclass
class AskResult:
    answer: str
    sources: list[SearchResult] = field(default_factory=list)


def ask(query: str, top_k: int = 5) -> AskResult:
    results = search(query, top_k=top_k)

    if not results:
        return AskResult(answer="知識庫裡目前沒有相關的筆記可以回答這個問題。")

    context = "\n\n".join(
        f"[來源: {result.document.title}]\n{result.chunk.content}" for result in results
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=ANSWER_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"筆記內容:\n\n{context}\n\n問題:{query}",
            }
        ],
    )

    answer = "".join(block.text for block in response.content if block.type == "text")
    return AskResult(answer=answer, sources=results)
