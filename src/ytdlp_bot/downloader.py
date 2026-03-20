from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from ytdlp_bot.config import Settings

logger = logging.getLogger(__name__)


class DownloadError(RuntimeError):
    """Raised when yt-dlp cannot download a video."""


@dataclass(slots=True)
class DownloadResult:
    file_path: str
    title: str
    duration: int | None
    file_size: int


class Downloader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.download_dir.mkdir(parents=True, exist_ok=True)

    def download(self, url: str) -> DownloadResult:
        options = self._build_options()
        logger.info("Start downloading video: %s", url)
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = self._resolve_file_path(ydl, info)
        except YtDlpDownloadError as exc:
            raise DownloadError(str(exc)) from exc
        except OSError as exc:
            raise DownloadError(f"无法写入下载文件：{exc}") from exc

        if not file_path.exists():
            raise DownloadError("下载完成，但找不到输出文件")

        return DownloadResult(
            file_path=str(file_path),
            title=str(info.get("title") or file_path.stem),
            duration=self._coerce_duration(info.get("duration")),
            file_size=file_path.stat().st_size,
        )

    def _build_options(self) -> dict[str, Any]:
        output_template = self.settings.download_dir / "%(title).200B-%(id)s.%(ext)s"
        options: dict[str, Any] = {
            "format": f"(bv*+ba/b)[filesize<{self.settings.max_file_size}]/(bv*+ba/b)",
            "merge_output_format": "mp4",
            "format_sort": ["ext:mp4:m4a", "res", "fps", "br"],
            "outtmpl": str(output_template),
            "restrictfilenames": True,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        if self.settings.proxy_url:
            options["proxy"] = self.settings.proxy_url
        return options

    def _resolve_file_path(self, ydl: YoutubeDL, info: dict[str, Any]) -> Path:
        requested_downloads = info.get("requested_downloads")
        if isinstance(requested_downloads, list):
            for entry in requested_downloads:
                if not isinstance(entry, dict):
                    continue
                filepath = entry.get("filepath")
                if isinstance(filepath, str) and filepath:
                    return Path(filepath)

        prepared = Path(ydl.prepare_filename(info))
        if prepared.exists():
            return prepared

        mp4_variant = prepared.with_suffix(".mp4")
        if mp4_variant.exists():
            return mp4_variant

        for sibling in prepared.parent.glob(f"{prepared.stem}.*"):
            if sibling.is_file():
                return sibling

        return mp4_variant

    def _coerce_duration(self, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return None
