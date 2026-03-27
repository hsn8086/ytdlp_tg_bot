from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import requests
import telebot
from telebot import apihelper
from telebot.apihelper import ApiTelegramException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from ytdlp_bot.ads import AdManager
from ytdlp_bot.config import Settings
from ytdlp_bot.db import Database
from ytdlp_bot.downloader import Downloader, DownloadError, DownloadResult
from ytdlp_bot.patterns import extract_urls

logger = logging.getLogger(__name__)

MessageLike = Any


class VideoBot:
    def __init__(
        self,
        settings: Settings,
        bot: Any | None = None,
        downloader: Any | None = None,
        db: Database | None = None,
        ad_manager: AdManager | None = None,
    ) -> None:
        self.settings = settings
        self._configure_proxy()
        self._configure_api_url()
        self.bot = bot or telebot.TeleBot(self.settings.telegram_bot_token)
        self.downloader = downloader or Downloader(settings)
        self.db = db or Database(self.settings.data_dir)
        self.ad_manager = ad_manager or AdManager(self.settings.data_dir)
        self.semaphore = threading.Semaphore(self.settings.max_concurrent_downloads)
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
        chat_id = message.chat.id

        # Check daily quota
        used_bytes = self.db.get_today_usage(chat_id)
        if used_bytes >= self.settings.daily_quota_mb * 1024 * 1024:
            self.bot.send_message(chat_id, "❌ 今日下载额度已耗尽")
            return

        status_message = self.bot.reply_to(message, "⏳ 排队中...")
        self.semaphore.acquire()
        self._update_status(status_message, "📥 正在下载...")

        logger.info("Processing %s url: %s", platform, url)
        self.db.increment_call_count()
        temporary_files: set[Path] = set()
        try:
            result = self.downloader.download(url)
            send_path = Path(result.file_path)
            temporary_files.add(send_path)

            if result.file_size > self.settings.max_file_size:
                max_mb = self.settings.max_file_size / (1024 * 1024)
                self.bot.send_message(chat_id, f"❌ 视频过大（超过 {max_mb:.0f}MB），无法发送")
                return

            self._update_status(status_message, "📤 正在上传...")
            self._send_video(message, result, send_path, url, used_bytes)
            self.db.add_usage(chat_id, result.file_size)

        except DownloadError as exc:
            self.bot.send_message(chat_id, f"❌ 下载失败：{exc}")
        except requests.RequestException:
            logger.exception("Network error while processing %s", url)
            self.bot.send_message(chat_id, "❌ 网络错误，请稍后重试")
        except Exception:
            logger.exception("Unexpected error while processing %s", url)
            self.bot.send_message(chat_id, "❌ 下载失败：服务暂时不可用")
        finally:
            self._cleanup_files(temporary_files)
            self._delete_status(status_message)
            self.semaphore.release()

    def _update_status(self, status_message: Any, text: str) -> None:
        try:
            self.bot.edit_message_text(text, status_message.chat.id, status_message.message_id)
        except ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = e.result_json.get("parameters", {}).get("retry_after", 3)
                logger.warning(
                    "Rate limited by Telegram. Retrying after %d seconds...", retry_after
                )
                time.sleep(retry_after)
                try:
                    self.bot.edit_message_text(
                        text, status_message.chat.id, status_message.message_id
                    )
                except Exception as ex:
                    logger.debug("Failed to edit message after retry: %s", ex)
            else:
                logger.debug("Failed to edit status message", exc_info=True)
        except Exception as e:
            logger.debug("Failed to edit status message: %s", e)

    def _send_video(
        self, message: Any, result: DownloadResult, path: Path, url: str, used_bytes: int
    ) -> None:
        safe_title = result.title.replace("<", "&lt;").replace(">", "&gt;")
        caption = f"{safe_title}\n\n<a href='{url}'>原视频</a> | {self.settings.bot_username}"
        if len(caption) > 1024:
            # If too long, truncate title
            allowed_title_len = (
                1024 - len(f"\n\n<a href='{url}'>原视频</a> | {self.settings.bot_username}") - 3
            )
            caption = f"{safe_title[:allowed_title_len]}...\n\n<a href='{url}'>原视频</a> | {self.settings.bot_username}"

        reply_markup = None
        if used_bytes >= self.settings.ad_threshold_mb * 1024 * 1024:
            ads = self.ad_manager.get_ads()
            if ads:
                reply_markup = InlineKeyboardMarkup()
                for ad in ads:
                    reply_markup.add(InlineKeyboardButton(text=ad["title"], url=ad["url"]))
                    self.db.increment_ad_trigger(ad["title"])

        with path.open("rb") as video_file:
            retry_count = 3
            while retry_count > 0:
                try:
                    self.bot.send_video(
                        message.chat.id,
                        video_file,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                        reply_to_message_id=message.message_id,
                        supports_streaming=True,
                    )
                    break
                except ApiTelegramException as e:
                    if e.error_code == 429:
                        retry_after = e.result_json.get("parameters", {}).get("retry_after", 5)
                        logger.warning(
                            "Rate limited when sending video. Retrying after %d seconds...",
                            retry_after,
                        )
                        time.sleep(retry_after)
                        retry_count -= 1
                    else:
                        raise e

    def _cleanup_files(self, paths: set[Path]) -> None:
        for path in paths:
            path.unlink(missing_ok=True)

    def _delete_status(self, status_message: Any) -> None:
        try:
            self.bot.delete_message(status_message.chat.id, status_message.message_id)
        except Exception:
            logger.debug("Failed to delete status message", exc_info=True)

    def _send_daily_report(self, report_date: str | None = None) -> None:
        admin_id = self.settings.admin_chat_id
        if not admin_id:
            return
        try:
            report = self.db.get_daily_report(report_date)
            total_mb = report["total_bytes"] / (1024 * 1024)
            lines = [
                f"📊 日报 - {report['date']}",
                f"",
                f"调用次数: {report['call_count']}",
                f"独立用户: {report['unique_users']}",
                f"总流量: {total_mb:.1f} MB",
            ]
            if report["ad_stats"]:
                lines.append("")
                lines.append("广告触发统计:")
                for ad_title, count in report["ad_stats"]:
                    lines.append(f"  • {ad_title}: {count} 次")
            else:
                lines.append("")
                lines.append("广告触发: 无")

            self.bot.send_message(admin_id, "\n".join(lines))
            logger.info("Daily report sent to %s", admin_id)
        except Exception:
            logger.exception("Failed to send daily report")

    def _start_report_scheduler(self) -> None:
        if not self.settings.admin_chat_id:
            logger.info("ADMIN_CHAT_ID not set, daily report disabled")
            return

        def scheduler():
            while True:
                now = datetime.now()
                tomorrow = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=5, microsecond=0
                )
                wait_seconds = (tomorrow - now).total_seconds()
                logger.info("Next daily report in %.0f seconds (at %s)", wait_seconds, tomorrow)
                time.sleep(wait_seconds)
                report_date = (tomorrow - timedelta(days=1)).date().isoformat()
                self._send_daily_report(report_date)

        thread = threading.Thread(target=scheduler, daemon=True)
        thread.start()
        logger.info("Daily report scheduler started")

    def run(self) -> None:
        logger.info("Bot polling started")
        self._start_report_scheduler()
        self.bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
