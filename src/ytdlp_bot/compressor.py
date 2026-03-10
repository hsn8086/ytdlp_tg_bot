from __future__ import annotations

import logging
from pathlib import Path
import subprocess

from ytdlp_bot.config import Settings

logger = logging.getLogger(__name__)


class Compressor:
    audio_bitrate_kbps = 128
    min_video_bitrate_kbps = 300

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def compress(self, input_path: str) -> str | None:
        source = Path(input_path)
        if not source.exists():
            raise FileNotFoundError(input_path)

        if source.stat().st_size <= self.settings.max_file_size:
            return str(source)

        duration = self._probe_duration(source)
        if duration is None or duration <= 0:
            logger.error("Could not determine duration for %s", input_path)
            return None

        output_path = source.with_name(f"{source.stem}.compressed.mp4")
        if output_path.exists():
            output_path.unlink()

        video_bitrate = self._calculate_video_bitrate(duration)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-b:v",
            f"{video_bitrate}k",
            "-maxrate",
            f"{video_bitrate}k",
            "-bufsize",
            f"{video_bitrate * 2}k",
            "-c:a",
            "aac",
            "-b:a",
            f"{self.audio_bitrate_kbps}k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.settings.compress_timeout,
            )
        except subprocess.TimeoutExpired:
            logger.exception("Compression timed out for %s", input_path)
            output_path.unlink(missing_ok=True)
            return None
        except subprocess.CalledProcessError:
            logger.exception("Compression failed for %s", input_path)
            output_path.unlink(missing_ok=True)
            return None

        if not output_path.exists():
            return None

        if output_path.stat().st_size > self.settings.max_file_size:
            logger.warning("Compressed file is still too large: %s", output_path)
            output_path.unlink(missing_ok=True)
            return None

        return str(output_path)

    def _probe_duration(self, path: Path) -> float | None:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            logger.exception("ffprobe failed for %s", path)
            return None

        output = result.stdout.strip()
        if not output:
            return None

        try:
            return float(output)
        except ValueError:
            return None

    def _calculate_video_bitrate(self, duration_seconds: float) -> int:
        total_kilobits = (self.settings.target_file_size * 8) / 1024
        target_total_bitrate = total_kilobits / duration_seconds
        target_video_bitrate = int(target_total_bitrate - self.audio_bitrate_kbps)
        return max(target_video_bitrate, self.min_video_bitrate_kbps)
