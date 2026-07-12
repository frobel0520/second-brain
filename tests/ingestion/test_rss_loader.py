import pytest

from second_brain.ingestion.rss_loader import get_feed_title, load_feed

_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>第一篇文章</title>
      <link>https://example.com/posts/1</link>
      <description>&lt;p&gt;這是 &lt;b&gt;第一篇&lt;/b&gt; 文章的內容,長度足夠不會被當成佔位文字。&lt;/p&gt;</description>
    </item>
    <item>
      <title>第二篇文章</title>
      <link>https://example.com/posts/2</link>
      <description>這是第二篇文章的完整內容,一樣故意寫長一點避免觸發內容過短的 fallback。</description>
    </item>
    <item>
      <title>第三篇文章</title>
      <link>https://example.com/posts/3</link>
      <description>這是第三篇文章的完整內容,同樣故意寫長一點避免觸發內容過短的 fallback。</description>
    </item>
  </channel>
</rss>
"""

_SPARSE_CONTENT_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sparse Feed</title>
    <item>
      <title>Article One</title>
      <link>https://example.com/sparse/1</link>
      <description>Comments</description>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/sparse/2</link>
      <description>Comments</description>
    </item>
  </channel>
</rss>
"""


def test_load_feed_returns_one_document_per_entry() -> None:
    documents = load_feed(_RSS_FEED)

    assert len(documents) == 3
    assert [d.title for d in documents] == ["第一篇文章", "第二篇文章", "第三篇文章"]


def test_load_feed_uses_link_as_source_path() -> None:
    documents = load_feed(_RSS_FEED)

    assert documents[0].source_path == "https://example.com/posts/1"


def test_load_feed_strips_html_from_content() -> None:
    documents = load_feed(_RSS_FEED)

    assert "<" not in documents[0].content
    assert "第一篇" in documents[0].content


def test_load_feed_respects_limit() -> None:
    documents = load_feed(_RSS_FEED, limit=2)

    assert len(documents) == 2


def test_load_feed_raises_for_unparseable_source() -> None:
    with pytest.raises(ValueError):
        load_feed("this is not a feed at all")


def test_get_feed_title_returns_channel_title() -> None:
    assert get_feed_title(_RSS_FEED) == "Test Feed"


def test_get_feed_title_returns_none_for_unparseable_source() -> None:
    assert get_feed_title("this is not a feed at all") is None


def test_load_feed_falls_back_to_title_when_content_too_short() -> None:
    """Hacker News 的 RSS description 只有「Comments」這種佔位文字,不是真正的
    文章內容;如果直接拿這種太短的內容當 dedupe 比對基準,不同文章會互相
    誤判成「同一篇改名」而被覆蓋掉(見 storage/store.py 的內容比對 fallback)。
    """
    documents = load_feed(_SPARSE_CONTENT_FEED)

    assert documents[0].content == "Article One"
    assert documents[1].content == "Article Two"
    assert documents[0].content != documents[1].content
