"""Signal-related command handlers (/signals)."""

from __future__ import annotations

import httpx
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.api_client import BotAPIClient
from bot.formatters import format_signal_list, format_signal_stats
from bot.keyboards import back_keyboard

logger = structlog.get_logger(__name__)

router = Router(name="signals")

VALID_SEVERITIES = {"critical", "high", "medium", "low"}


# ------------------------------------------------------------------
# /signals [severity]
# ------------------------------------------------------------------


@router.message(Command("signals"))
async def cmd_signals(message: Message, api: BotAPIClient) -> None:
    """Show recent signals, optionally filtered by severity.

    Usage:
        /signals           -- last 10 signals of any severity
        /signals critical   -- only critical signals
        /signals high       -- only high-severity signals
    """
    severity = _parse_severity(message.text)
    try:
        signals = await api.get_signals(severity=severity, limit=15)
        text = format_signal_list(signals)
        if severity:
            text = f"<i>Filter: {severity}</i>\n\n" + text
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_signals_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_signals_error")
        await message.answer("Failed to fetch signals.")


@router.callback_query(lambda cb: cb.data == "cmd:signals")
async def cb_signals(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle inline button for signals."""
    await callback.answer()
    try:
        signals = await api.get_signals(limit=15)
        text = format_signal_list(signals)
        if callback.message:
            await callback.message.edit_text(
                text, parse_mode="HTML", reply_markup=back_keyboard()
            )
    except Exception:
        logger.exception("cb_signals_error")
        if callback.message:
            await callback.message.edit_text("Failed to fetch signals.")


# ------------------------------------------------------------------
# /signalstats (bonus -- signal statistics overview)
# ------------------------------------------------------------------


@router.message(Command("signalstats"))
async def cmd_signal_stats(message: Message, api: BotAPIClient) -> None:
    """Show signal count statistics."""
    try:
        stats = await api.get_signal_stats()
        text = format_signal_stats(stats)
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_signal_stats_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_signal_stats_error")
        await message.answer("Failed to fetch signal stats.")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_severity(text: str | None) -> str | None:
    """Extract an optional severity argument from '/signals critical'."""
    if not text:
        return None
    parts = text.strip().split()
    if len(parts) >= 2:
        candidate = parts[1].lower()
        if candidate in VALID_SEVERITIES:
            return candidate
    return None
