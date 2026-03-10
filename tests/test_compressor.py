from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from ytdlp_bot.compressor import Compressor
from ytdlp_bot.config import Settings


def test_compressor_returns_input_when_already_small(tmp_path: Path) -> None:
    input_file = tmp_path / "small.mp4"
    input_file.write_bytes(b"1234")
    compressor = Compressor(Settings(TELEGRAM_BOT_TOKEN="token", max_file_size=10))

    assert compressor.compress(str(input_file)) == str(input_file)


def test_compressor_compresses_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_file = tmp_path / "large.mp4"
    input_file.write_bytes(b"x" * 200)
    output_file = tmp_path / "large.compressed.mp4"
    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        max_file_size=150,
        target_file_size=120,
        compress_timeout=20,
    )
    compressor = Compressor(settings)

    def fake_run(
        command: list[str], check: bool, capture_output: bool, text: bool, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(command, 0, stdout="10.0\n", stderr="")

        output_file.write_bytes(b"y" * 100)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ytdlp_bot.compressor.subprocess.run", fake_run)

    result = compressor.compress(str(input_file))

    assert result == str(output_file)


def test_compressor_returns_none_when_output_still_too_large(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    input_file = tmp_path / "large.mp4"
    input_file.write_bytes(b"x" * 300)
    output_file = tmp_path / "large.compressed.mp4"
    compressor = Compressor(
        Settings(TELEGRAM_BOT_TOKEN="token", max_file_size=150, target_file_size=120)
    )

    def fake_run(
        command: list[str], check: bool, capture_output: bool, text: bool, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(command, 0, stdout="5.0\n", stderr="")

        output_file.write_bytes(b"y" * 200)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("ytdlp_bot.compressor.subprocess.run", fake_run)

    assert compressor.compress(str(input_file)) is None
    assert not output_file.exists()
