from __future__ import annotations

import re

MatchedUrl = tuple[str, str]

_URL_SUFFIX = r"[^\s<>()\[\]{}\"']*"

PATTERNS: dict[str, re.Pattern[str]] = {
    "youtube": re.compile(
        rf"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s]*?v=[\w-]{{11}}{_URL_SUFFIX}|youtube\.com/shorts/[\w-]+{_URL_SUFFIX}|youtu\.be/[\w-]+{_URL_SUFFIX})",
        re.IGNORECASE,
    ),
    "bilibili": re.compile(
        rf"https?://(?:www\.)?(?:bilibili\.com/video/[A-Za-z0-9]+{_URL_SUFFIX}|b23\.tv/[A-Za-z0-9]+{_URL_SUFFIX})",
        re.IGNORECASE,
    ),
    "twitter": re.compile(
        rf"https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+/status/\d+{_URL_SUFFIX}",
        re.IGNORECASE,
    ),
}

_TRAILING_PUNCTUATION = ".,!?;:)]}"


def extract_urls(text: str) -> list[MatchedUrl]:
    matches: list[tuple[int, MatchedUrl]] = []
    for platform, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
            matches.append((match.start(), (url, platform)))

    matches.sort(key=lambda item: item[0])
    return [item[1] for item in matches]
