from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_api_url: str | None = Field(default=None, alias="TELEGRAM_API_URL")
    proxy_url: str | None = Field(default=None, alias="PROXY_URL")
    download_dir: Path = Field(default=Path("/tmp/ytdlp_bot_downloads"), alias="DOWNLOAD_DIR")
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    max_file_size: int = Field(default=2000 * 1024 * 1024, alias="MAX_FILE_SIZE")

    # New features
    bot_username: str = Field(default="@hsn_viddl_bot", alias="BOT_USERNAME")
    daily_quota_mb: int = Field(default=5000, alias="DAILY_QUOTA_MB")
    ad_threshold_mb: int = Field(default=1000, alias="AD_THRESHOLD_MB")
    max_concurrent_downloads: int = Field(default=3, alias="MAX_CONCURRENT_DOWNLOADS")
    admin_chat_id: int | None = Field(default=None, alias="ADMIN_CHAT_ID")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("proxy_url", mode="before")
    @classmethod
    def validate_proxy_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https", "socks5", "socks5h"}:
            msg = "PROXY_URL must start with http://, https://, socks5://, or socks5h://"
            raise ValueError(msg)
        if not parsed.netloc:
            raise ValueError("PROXY_URL must include host and port")
        return normalized

    @field_validator("download_dir", "data_dir", mode="before")
    @classmethod
    def validate_dir(cls, value: str | Path) -> Path:
        return Path(value).expanduser()

    @field_validator("max_file_size", "daily_quota_mb", "max_concurrent_downloads")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be positive")
        return value


def load_settings() -> Settings:
    return cast(Any, Settings)()
