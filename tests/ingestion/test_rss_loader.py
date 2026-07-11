import pytest

from second_brain.ingestion.rss_loader import load_feed

_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>第一篇文章</title>
      <link>https://example.com/posts/1</link>
      <description>&lt;p&gt;這是 &lt;b&gt;第一篇&lt;/b&gt; 文章的內容。&lt;/p&gt;</description>
    </item>
    <item>
      <title>第二篇文章</title>
      <link>https://example.com/posts/2</link>
      <description>第二篇的內容。</description>
    </item>
    <item>
      <title>第三篇文章</title>
      <link>https://example.com/posts/3</link>
      <description>第三篇的內容。</description>
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
