"""RSS/Atom 訂閱來源的 loader。只負責「抓 feed → 轉成 Document 列表」,不碰 embedding/儲存。"""

from __future__ import annotations

import html
import re
import uuid
from typing import Any

from second_brain.models import Document

_TAG_RE = re.compile(r"<[^>]+>")

# 有些 feed(例如 Hacker News)的 description 只有「Comments」這種佔位文字,
# 不是真正的文章內容。太短的內容當 dedupe 比對基準會讓不同文章互相誤判成
# 「同一篇改名」(見 storage/store.py:replace_existing_document 的內容比對
# fallback),所以內容太短就退回用標題,至少同一批裡不會互相撞在一起。
_MIN_CONTENT_LENGTH = 20


def load_feed(feed_url: str, limit: int | None = None) -> list[Document]:
    """抓取並解析 RSS/Atom 來源,每篇文章轉成一個 Document。

    `feed_url` 可以是網址,也可以是本機檔案路徑或 feed 原始內容
    (由 feedparser 自動判斷),方便測試/離線驗證。
    """
    import feedparser

    parsed = feedparser.parse(feed_url)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"無法解析這個 RSS/Atom 來源: {feed_url}")

    entries = parsed.entries[:limit] if limit else parsed.entries
    return [_entry_to_document(entry) for entry in entries]


def get_feed_title(feed_url: str) -> str | None:
    """抓 feed 的頻道標題,拿不到就回傳 None(呼叫端可以退回用網址本身當名稱)。"""
    import feedparser

    parsed = feedparser.parse(feed_url)
    title = parsed.feed.get("title")
    return title.strip() if title else None


def _entry_to_document(entry: Any) -> Document:
    link = entry.get("link") or entry.get("id") or str(uuid.uuid4())
    title = entry.get("title", "").strip() or link
    content = _strip_html(_extract_raw_content(entry))
    if len(content) < _MIN_CONTENT_LENGTH:
        content = title

    return Document(
        id=str(uuid.uuid4()),
        source_path=link,
        title=title,
        content=content,
        metadata={"source_type": "rss"},
    )


def _extract_raw_content(entry: Any) -> str:
    if entry.get("content"):
        return entry.content[0].value
    return entry.get("summary", "")


def _strip_html(raw: str) -> str:
    """粗略去掉 HTML 標籤,不是完整的 HTML parser,遇到不規則標記可能會有殘留。"""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()
