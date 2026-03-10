"""Handler registration for the Telegram bot.

Import and include all handler routers so that the dispatcher
picks up every command.
"""

from __future__ import annotations

from aiogram import Dispatcher

from bot.handlers.reports import router as reports_router
from bot.handlers.search import router as search_router
from bot.handlers.settings import router as settings_router
from bot.handlers.signals import router as signals_router
from bot.handlers.start import router as start_router


def register_handlers(dp: Dispatcher) -> None:
    """Include all handler routers into the dispatcher."""
    dp.include_router(start_router)
    dp.include_router(reports_router)
    dp.include_router(signals_router)
    dp.include_router(search_router)
    dp.include_router(settings_router)
