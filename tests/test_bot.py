from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from ytdlp_bot.bot import VideoBot
from ytdlp_bot.config import Settings
from ytdlp_bot.downloader import DownloadError, DownloadResult


@dataclass
class FakeMessage:
    chat: SimpleNamespace
    message_id: int
    text: str | None = None


class FakeBot:
    def __init__(self) -> None:
        self.handlers: list[dict[str, Any]] = []
        self.replies: list[str] = []
        self.sent_messages: list[str] = []
        self.edits: list[str] = []
        self.sent_videos: list[dict[str, Any]] = []
        self.deleted_messages: list[tuple[int, int]] = []

    def message_handler(self, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.handlers.append({"kwargs": kwargs, "func": func})
            return func

        return decorator

    def reply_to(self, message: FakeMessage, text: str) -> FakeMessage:
        self.replies.append(text)
        return FakeMessage(chat=message.chat, message_id=999, text=text)

    def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append(text)

    def edit_message_text(self, text: str, chat_id: int, message_id: int) -> None:
        self.edits.append(text)

    def send_video(
        self,
        chat_id: int,
        video: Any,
        caption: str,
        reply_to_message_id: int,
        supports_streaming: bool,
    ) -> None:
        self.sent_videos.append(
            {
                "chat_id": chat_id,
                "caption": caption,
                "reply_to_message_id": reply_to_message_id,
                "supports_streaming": supports_streaming,
                "name": getattr(video, "name", ""),
            }
        )

    def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted_messages.append((chat_id, message_id))

    def infinity_polling(self, **kwargs: Any) -> None:
        return None


class StubDownloader:
    def __init__(self, result: DownloadResult | Exception) -> None:
        self.result = result

    def download(self, url: str) -> DownloadResult:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class StubCompressor:
    def __init__(self, result: str | None) -> None:
        self.result = result

    def compress(self, input_path: str) -> str | None:
        return self.result


def test_start_and_help_handlers_reply_with_help_text() -> None:
    fake_bot = FakeBot()
    bot = VideoBot(Settings(TELEGRAM_BOT_TOKEN="token"), bot=fake_bot)
    help_handler = fake_bot.handlers[0]["func"]
    message = FakeMessage(chat=SimpleNamespace(id=1), message_id=1, text="/start")

    help_handler(message)

    assert "直接发送视频链接即可开始下载" in fake_bot.replies[-1]
    assert bot._has_supported_urls("https://youtu.be/dQw4w9WgXcQ") is True


def test_process_video_sends_downloaded_file_and_cleans_up(tmp_path: Path) -> None:
    video_file = tmp_path / "demo.mp4"
    video_file.write_bytes(b"video")
    fake_bot = FakeBot()
    downloader = StubDownloader(
        DownloadResult(
            file_path=str(video_file),
            title="Demo title",
            duration=10,
            file_size=video_file.stat().st_size,
        )
    )
    bot = VideoBot(
        Settings(TELEGRAM_BOT_TOKEN="token", max_file_size=10),
        bot=fake_bot,
        downloader=downloader,
        compressor=StubCompressor(None),
    )
    message = FakeMessage(
        chat=SimpleNamespace(id=100), message_id=42, text="https://youtu.be/dQw4w9WgXcQ"
    )

    bot._process_video(message, "https://youtu.be/dQw4w9WgXcQ", "youtube")

    assert fake_bot.sent_videos[0]["caption"] == "Demo title"
    assert fake_bot.deleted_messages == [(100, 999)]
    assert not video_file.exists()


def test_process_video_compresses_large_file_before_sending(tmp_path: Path) -> None:
    source_file = tmp_path / "demo.mp4"
    source_file.write_bytes(b"x" * 20)
    compressed_file = tmp_path / "demo.compressed.mp4"
    compressed_file.write_bytes(b"y" * 5)
    fake_bot = FakeBot()
    downloader = StubDownloader(
        DownloadResult(
            file_path=str(source_file),
            title="Compressed demo",
            duration=20,
            file_size=source_file.stat().st_size,
        )
    )
    compressor = StubCompressor(str(compressed_file))
    bot = VideoBot(
        Settings(TELEGRAM_BOT_TOKEN="token", max_file_size=10),
        bot=fake_bot,
        downloader=downloader,
        compressor=compressor,
    )
    message = FakeMessage(
        chat=SimpleNamespace(id=100), message_id=42, text="https://youtu.be/dQw4w9WgXcQ"
    )

    bot._process_video(message, "https://youtu.be/dQw4w9WgXcQ", "youtube")

    assert fake_bot.edits == ["📦 正在处理..."]
    assert fake_bot.sent_videos[0]["name"].endswith("demo.compressed.mp4")
    assert not source_file.exists()
    assert not compressed_file.exists()


def test_process_video_reports_download_error() -> None:
    fake_bot = FakeBot()
    downloader = StubDownloader(DownloadError("失败原因"))
    bot = VideoBot(
        Settings(TELEGRAM_BOT_TOKEN="token"),
        bot=fake_bot,
        downloader=downloader,
        compressor=StubCompressor(None),
    )
    message = FakeMessage(
        chat=SimpleNamespace(id=100), message_id=42, text="https://youtu.be/dQw4w9WgXcQ"
    )

    bot._process_video(message, "https://youtu.be/dQw4w9WgXcQ", "youtube")

    assert fake_bot.sent_messages == ["❌ 下载失败：失败原因"]


def test_unknown_link_handler_reports_unrecognized_url() -> None:
    fake_bot = FakeBot()
    VideoBot(Settings(TELEGRAM_BOT_TOKEN="token"), bot=fake_bot)
    unknown_handler = fake_bot.handlers[2]["func"]
    message = FakeMessage(chat=SimpleNamespace(id=1), message_id=1, text="https://example.com")

    unknown_handler(message)

    assert fake_bot.replies[-1] == "❌ 无法识别该链接"
