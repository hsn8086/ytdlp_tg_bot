from __future__ import annotations

from ytdlp_bot.patterns import extract_urls


def test_extract_urls_supports_multiple_platforms() -> None:
    text = (
        "看看这个 https://www.youtube.com/watch?v=dQw4w9WgXcQ ，"
        "还有 https://b23.tv/abc123 和 https://x.com/demo/status/1234567890"
    )

    assert extract_urls(text) == [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://b23.tv/abc123", "bilibili"),
        ("https://x.com/demo/status/1234567890", "twitter"),
    ]


def test_extract_urls_ignores_non_video_links() -> None:
    text = "频道页 https://www.youtube.com/@demo 和主页 https://x.com/demo 都不应该匹配"

    assert extract_urls(text) == []


def test_extract_urls_matches_shorts_and_status_urls() -> None:
    text = "shorts: https://youtube.com/shorts/abcDEF12345?t=3. tweet: https://twitter.com/demo/status/12345?s=20"

    assert extract_urls(text) == [
        ("https://youtube.com/shorts/abcDEF12345?t=3", "youtube"),
        ("https://twitter.com/demo/status/12345?s=20", "twitter"),
    ]
