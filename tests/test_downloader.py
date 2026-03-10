from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from ytdlp_bot.config import Settings
from ytdlp_bot.downloader import DownloadError, Downloader


class FakeYoutubeDL:
    def __init__(
        self, options: dict[str, Any], info: dict[str, Any], prepared_filename: str
    ) -> None:
        self.options = options
        self._info = info
        self._prepared_filename = prepared_filename

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def extract_info(self, url: str, download: bool) -> dict[str, Any]:
        assert url == "https://example.com/video"
        assert download is True
        return self._info

    def prepare_filename(self, info: dict[str, Any]) -> str:
        assert info is self._info
        return self._prepared_filename


def test_downloader_returns_download_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", download_dir=tmp_path)
    target_file = tmp_path / "demo-123.mp4"
    target_file.write_bytes(b"video-data")
    info = {
        "title": "Demo",
        "duration": 12.8,
        "requested_downloads": [{"filepath": str(target_file)}],
    }

    def fake_factory(options: dict[str, Any]) -> FakeYoutubeDL:
        assert options["proxy"] == "http://127.0.0.1:7890"
        return FakeYoutubeDL(options, info, str(target_file.with_suffix(".mkv")))

    monkeypatch.setattr("ytdlp_bot.downloader.YoutubeDL", fake_factory)
    downloader = Downloader(
        Settings(
            TELEGRAM_BOT_TOKEN="token",
            download_dir=tmp_path,
            proxy_url="http://127.0.0.1:7890",
        )
    )

    result = downloader.download("https://example.com/video")

    assert result.file_path == str(target_file)
    assert result.title == "Demo"
    assert result.duration == 12
    assert result.file_size == len(b"video-data")


def test_downloader_falls_back_to_mp4_variant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", download_dir=tmp_path)
    actual_file = tmp_path / "demo-123.mp4"
    actual_file.write_bytes(b"video")
    info = {"title": "Demo", "duration": None}

    def fake_factory(options: dict[str, Any]) -> FakeYoutubeDL:
        return FakeYoutubeDL(options, info, str(tmp_path / "demo-123.webm"))

    monkeypatch.setattr("ytdlp_bot.downloader.YoutubeDL", fake_factory)
    downloader = Downloader(settings)

    result = downloader.download("https://example.com/video")

    assert result.file_path == str(actual_file)


def test_downloader_wraps_ytdlp_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", download_dir=tmp_path)

    class RaisingYoutubeDL:
        def __init__(self, options: dict[str, Any]) -> None:
            self.options = options

        def __enter__(self) -> "RaisingYoutubeDL":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, Any]:
            raise YtDlpDownloadError("boom")

    monkeypatch.setattr("ytdlp_bot.downloader.YoutubeDL", RaisingYoutubeDL)
    downloader = Downloader(settings)

    with pytest.raises(DownloadError, match="boom"):
        downloader.download("https://example.com/video")
