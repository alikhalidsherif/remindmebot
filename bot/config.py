"""Configuration helpers for the Telegram reminder bot."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Config:
    """Application configuration loaded from environment variables."""

    telegram_bot_token: str
    default_timezone: str
    log_level: str
    database_url: str
    nominatim_user_agent: str

    @property
    def sqlite_path(self) -> Path | None:
        """Return the SQLite file path when using SQLite, else ``None``."""
        if self.database_url.startswith("sqlite"):
            # URLs look like ``sqlite+aiosqlite:///path/to/db``
            raw_path = self.database_url.split("///", maxsplit=1)[-1]
            # Ensure the path is absolute
            if not raw_path.startswith("/"):
                raw_path = "/" + raw_path
            return Path(raw_path)
        return None


def load_config() -> Config:
    """Load configuration from environment variables."""

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    default_timezone = os.getenv("DEFAULT_TIMEZONE", "UTC")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    nominatim_user_agent = os.getenv("NOMINATIM_USER_AGENT", "telegram-reminder-bot")

    database_url = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///data/reminders.db",
    )

    config = Config(
        telegram_bot_token=telegram_bot_token,
        default_timezone=default_timezone,
        log_level=log_level,
        database_url=database_url,
        nominatim_user_agent=nominatim_user_agent,
    )

    sqlite_path = config.sqlite_path
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    return config
