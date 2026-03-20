from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import requests
import telebot
from telebot import apihelper

from ytdlp_bot.config import Settings
from ytdlp_bot.downloader import DownloadError, DownloadResult, Downloader
from ytdlp_bot.patterns import extract_urls

logger = logging.getLogger(__name__)

MessageLike = Any


class VideoBot:
    def __init__(
        self,
        settings: Settings,
        bot: Any | None = None,
        downloader: Any | None = None,
    ) -> None:
        self.settings = settings
        self._configure_proxy()
        self._configure_api_url()
        self.bot = bot or telebot.TeleBot(self.settings.telegram_bot_token)
        self.downloader = downloader or Downloader(settings)
        self._setup_handlers()

    def _configure_proxy(self) -> None:
        if self.settings.proxy_url:
            cast(Any, apihelper).proxy = {
                "http": self.settings.proxy_url,
                "https": self.settings.proxy_url,
            }

    def _configure_api_url(self) -> None:
        if self.settings.telegram_api_url:
            base_url = self.settings.telegram_api_url.rstrip("/")
            cast(Any, apihelper).API_URL = f"{base_url}/bot{{0}}/{{1}}"

    def _setup_handlers(self) -> None:
        @self.bot.message_handler(commands=["start", "help"])
        def handle_help(message: MessageLike) -> None:
            self.bot.reply_to(message, self._build_help_text())

        @self.bot.message_handler(
            func=lambda message: self._has_supported_urls(getattr(message, "text", None)),
            content_types=["text"],
        )
        def handle_video_links(message: MessageLike) -> None:
            text = message.text or ""
            for url, platform in extract_urls(text):
                self._process_video(message, url, platform)

        @self.bot.message_handler(
            func=lambda message: self._looks_like_url(getattr(message, "text", None)),
            content_types=["text"],
        )
        def handle_unknown_link(message: MessageLike) -> None:
            self.bot.reply_to(message, "❌ 无法识别该链接")

    def _build_help_text(self) -> str:
        return (
            "欢迎使用 ytdlp_bot。\n"
            "直接发送视频链接即可开始下载。\n\n"
            "当前支持：YouTube、Bilibili、X(Twitter)。\n"
            "命令：\n"
            "/start - 查看欢迎信息\n"
            "/help - 查看帮助说明"
        )

    def _has_supported_urls(self, text: str | None) -> bool:
        return bool(text and extract_urls(text))

    def _looks_like_url(self, text: str | None) -> bool:
        if not text:
            return False
        return "http://" in text or "https://" in text

    def _process_video(self, message: MessageLike, url: str, platform: str) -> None:
        logger.info("Processing %s url: %s", platform, url)
        status_message = self.bot.reply_to(message, "⏳ 正在下载...")
        temporary_files: set[Path] = set()
        try:
            result = self.downloader.download(url)
            send_path = Path(result.file_path)
            temporary_files.add(send_path)

            if result.file_size > self.settings.max_file_size:
                max_mb = self.settings.max_file_size / (1024 * 1024)
                self.bot.send_message(
                    message.chat.id, f"❌ 视频过大（超过 {max_mb:.0f}MB），无法发送"
                )
                return

            self._update_status(status_message, "📤 正在上传...")
            self._send_video(message, result, send_path)
        except DownloadError as exc:
            self.bot.send_message(message.chat.id, f"❌ 下载失败：{exc}")
        except requests.RequestException:
            logger.exception("Network error while processing %s", url)
            self.bot.send_message(message.chat.id, "❌ 网络错误，请稍后重试")
        except Exception:
            logger.exception("Unexpected error while processing %s", url)
            self.bot.send_message(message.chat.id, "❌ 下载失败：服务暂时不可用")
        finally:
            self._cleanup_files(temporary_files)
            self._delete_status(status_message)

    def _update_status(self, status_message: Any, text: str) -> None:
        self.bot.edit_message_text(text, status_message.chat.id, status_message.message_id)

    def _send_video(self, message: Any, result: DownloadResult, path: Path) -> None:
        caption = result.title[:1024]
        with path.open("rb") as video_file:
            self.bot.send_video(
                message.chat.id,
                video_file,
                caption=caption,
                reply_to_message_id=message.message_id,
                supports_streaming=True,
            )

    def _cleanup_files(self, paths: set[Path]) -> None:
        for path in paths:
            path.unlink(missing_ok=True)

    def _delete_status(self, status_message: Any) -> None:
        try:
            self.bot.delete_message(status_message.chat.id, status_message.message_id)
        except Exception:
            logger.debug("Failed to delete status message", exc_info=True)

    def run(self) -> None:
        logger.info("Bot polling started")
        self.bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
