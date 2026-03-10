"""Telegram bot configuration via Pydantic settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class BotSettings(BaseSettings):
    """Configuration for the Telegram bot subsystem.

    All values are read from environment variables.
    TELEGRAM_ALLOWED_USERS and TELEGRAM_ADMIN_USERS accept
    comma-separated Telegram chat/user IDs.
    """

    TELEGRAM_BOT_TOKEN: str = ""
    API_BASE_URL: str = "http://api:8000"
    TELEGRAM_ALLOWED_USERS: str = ""
    TELEGRAM_ADMIN_USERS: str = ""
    TELEGRAM_ENABLED: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def allowed_user_ids(self) -> list[int]:
        """Parse TELEGRAM_ALLOWED_USERS into a list of integer user IDs."""
        if not self.TELEGRAM_ALLOWED_USERS.strip():
            return []
        return [
            int(uid.strip())
            for uid in self.TELEGRAM_ALLOWED_USERS.split(",")
            if uid.strip().lstrip("-").isdigit()
        ]

    @property
    def admin_user_ids(self) -> list[int]:
        """Parse TELEGRAM_ADMIN_USERS into a list of integer user IDs."""
        if not self.TELEGRAM_ADMIN_USERS.strip():
            return []
        return [
            int(uid.strip())
            for uid in self.TELEGRAM_ADMIN_USERS.split(",")
            if uid.strip().lstrip("-").isdigit()
        ]


@lru_cache(maxsize=1)
def get_bot_settings() -> BotSettings:
    """Return a cached singleton of BotSettings."""
    return BotSettings()
