"""Entry point for the AI Trend Monitor Telegram bot.

Run with:
    python -m bot.main
"""

from __future__ import annotations

import asyncio
import sys

import structlog
from aiogram import Bot, Dispatcher

from bot.api_client import BotAPIClient
from bot.config import get_bot_settings
from bot.handlers import register_handlers
from bot.middleware import AuthMiddleware

logger = structlog.get_logger(__name__)


async def main() -> None:
    """Initialise the bot, wire up middleware and handlers, and start polling."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    settings = get_bot_settings()

    if not settings.TELEGRAM_ENABLED:
        logger.warning("telegram_disabled", reason="TELEGRAM_ENABLED is False")
        return

    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("telegram_token_missing", hint="Set TELEGRAM_BOT_TOKEN env var")
        sys.exit(1)

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    # HTTP client for the FastAPI backend
    api_client = BotAPIClient(settings.API_BASE_URL)

    # Auth middleware -- only applied when an explicit whitelist exists
    if settings.allowed_user_ids:
        dp.message.middleware(AuthMiddleware(settings.allowed_user_ids))
        logger.info(
            "auth_middleware_enabled",
            allowed_users=settings.allowed_user_ids,
        )
    else:
        logger.info("auth_middleware_disabled", reason="no allowed_user_ids configured")

    # Register all command / callback routers
    register_handlers(dp)

    # Make the API client available to every handler via keyword injection
    dp["api"] = api_client

    logger.info(
        "bot_starting",
        api_base_url=settings.API_BASE_URL,
    )

    try:
        await dp.start_polling(bot)
    finally:
        logger.info("bot_shutting_down")
        await api_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
