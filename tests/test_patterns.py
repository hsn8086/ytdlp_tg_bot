from __future__ import annotations

from ytdlp_bot.patterns import extract_urls


def test_extract_urls_supports_multiple_platforms() -> None:
    text = (
        "看看这个 https://www.youtube.com/watch?v=dQw4w9WgXcQ ，"
        "还有 https://b23.tv/abc123 和 https://x.com/demo/status/1234567890 "
        "以及 https://www.tiktok.com/@demo/video/1234567890123456789 "
        "https://www.instagram.com/reel/Cu123abcDEF/ "
        "https://vimeo.com/123456789 "
        "https://www.reddit.com/r/test/comments/abc123/example_post/xyz789/"
    )

    assert extract_urls(text) == [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://b23.tv/abc123", "bilibili"),
        ("https://x.com/demo/status/1234567890", "twitter"),
        ("https://www.tiktok.com/@demo/video/1234567890123456789", "tiktok"),
        ("https://www.instagram.com/reel/Cu123abcDEF/", "instagram"),
        ("https://vimeo.com/123456789", "vimeo"),
        (
            "https://www.reddit.com/r/test/comments/abc123/example_post/xyz789/",
            "reddit",
        ),
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


def test_extract_urls_matches_short_links_and_media_posts() -> None:
    text = (
        "TikTok 短链 https://vm.tiktok.com/ZMABC1234/ "
        "Reddit 视频 https://v.redd.it/abc123xyz "
        "Instagram 帖子 https://instagram.com/p/ABCdef12345/?utm_source=ig_web_copy_link"
    )

    assert extract_urls(text) == [
        ("https://vm.tiktok.com/ZMABC1234/", "tiktok"),
        ("https://v.redd.it/abc123xyz", "reddit"),
        (
            "https://instagram.com/p/ABCdef12345/?utm_source=ig_web_copy_link",
            "instagram",
        ),
    ]
