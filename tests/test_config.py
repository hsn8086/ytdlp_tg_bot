from __future__ import annotations

from pathlib import Path

import pytest

from ytdlp_bot.config import Settings


def test_settings_load_defaults() -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", _env_file=None)

    assert settings.telegram_bot_token == "token"
    assert settings.proxy_url is None
    assert settings.download_dir == Path("/tmp/ytdlp_bot_downloads")
    assert settings.max_file_size == 50 * 1024 * 1024
    assert settings.target_file_size == 48 * 1024 * 1024
    assert settings.compress_timeout == 300


def test_settings_normalize_proxy_url() -> None:
    settings = Settings(TELEGRAM_BOT_TOKEN="token", proxy_url="  socks5://127.0.0.1:7890  ")

    assert settings.proxy_url == "socks5://127.0.0.1:7890"


def test_settings_reject_invalid_proxy_scheme() -> None:
    with pytest.raises(ValueError):
        Settings(TELEGRAM_BOT_TOKEN="token", proxy_url="ftp://127.0.0.1:21")
