from second_brain.interface.cli import _format_sync_log_line
from second_brain.ingestion.pipeline import FeedSyncResult
from second_brain.models import FeedSubscription


def _feed(name: str) -> FeedSubscription:
    return FeedSubscription(id=name, url=f"https://example.com/{name}", name=name)


def test_format_sync_log_line_sums_added_and_updated_across_feeds() -> None:
    results = [
        FeedSyncResult(feed=_feed("a"), added=3, updated=1, skipped=0),
        FeedSyncResult(feed=_feed("b"), added=2, updated=4, skipped=0),
    ]

    line = _format_sync_log_line(results)

    assert "新增 5 篇" in line
    assert "更新 5 篇" in line
    assert "失敗 0 個來源" in line


def test_format_sync_log_line_lists_failed_feeds_with_reason() -> None:
    results = [
        FeedSyncResult(feed=_feed("a"), added=1, updated=0, skipped=0),
        FeedSyncResult(feed=_feed("b"), added=0, updated=0, skipped=0, error="timeout"),
    ]

    line = _format_sync_log_line(results)

    assert "失敗 1 個來源" in line
    assert "b 同步失敗:timeout" in line


def test_format_sync_log_line_starts_with_timestamp() -> None:
    line = _format_sync_log_line([FeedSyncResult(feed=_feed("a"), added=0, updated=0, skipped=0)])

    timestamp = line.split("  ")[0]
    assert len(timestamp) == len("2026-07-12 15:42:03")
