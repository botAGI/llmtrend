"""System and admin command handlers (/status, /settings, /collect, /analyze, /subscribe)."""

from __future__ import annotations

import httpx
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.api_client import BotAPIClient
from bot.config import get_bot_settings
from bot.formatters import format_status
from bot.keyboards import back_keyboard

logger = structlog.get_logger(__name__)

router = Router(name="settings")


# ------------------------------------------------------------------
# /status
# ------------------------------------------------------------------


@router.message(Command("status"))
async def cmd_status(message: Message, api: BotAPIClient) -> None:
    """Show current system status (database, ollama, collections)."""
    try:
        data = await api.get_status()
        text = format_status(data)
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_status_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_status_error")
        await message.answer("Failed to fetch system status.")


@router.callback_query(lambda cb: cb.data == "cmd:status")
async def cb_status(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle inline button for system status."""
    await callback.answer()
    try:
        data = await api.get_status()
        text = format_status(data)
        if callback.message:
            await callback.message.edit_text(
                text, parse_mode="HTML", reply_markup=back_keyboard()
            )
    except Exception:
        logger.exception("cb_status_error")
        if callback.message:
            await callback.message.edit_text("Failed to fetch system status.")


# ------------------------------------------------------------------
# /collect [source] -- admin only
# ------------------------------------------------------------------


@router.message(Command("collect"))
async def cmd_collect(message: Message, api: BotAPIClient) -> None:
    """Trigger data collection (admin only).

    Usage:
        /collect       -- collect from all sources
        /collect hf    -- collect from HuggingFace only
    """
    if not _is_admin(message):
        await message.answer("This command is restricted to administrators.")
        return

    source = _extract_arg(message.text) or "all"
    await message.answer(
        f"<i>Starting data collection (source: {source})...</i>",
        parse_mode="HTML",
    )
    try:
        result = await api.trigger_collection(source=source)
        task_id = result.get("task_id", "unknown")
        status = result.get("status", "unknown")
        await message.answer(
            f"Collection started.\n"
            f"Task ID: <code>{task_id}</code>\n"
            f"Status: <code>{status}</code>",
            parse_mode="HTML",
        )
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_collect_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_collect_error")
        await message.answer("Failed to trigger collection.")


@router.callback_query(lambda cb: cb.data == "confirm:collect")
async def cb_confirm_collect(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle confirmed collection trigger from inline keyboard."""
    await callback.answer("Starting collection...")
    try:
        result = await api.trigger_collection(source="all")
        task_id = result.get("task_id", "unknown")
        status = result.get("status", "unknown")
        if callback.message:
            await callback.message.edit_text(
                f"Collection started.\n"
                f"Task ID: <code>{task_id}</code>\n"
                f"Status: <code>{status}</code>",
                parse_mode="HTML",
            )
    except Exception:
        logger.exception("cb_confirm_collect_error")
        if callback.message:
            await callback.message.edit_text("Failed to trigger collection.")


# ------------------------------------------------------------------
# /analyze -- admin only
# ------------------------------------------------------------------


@router.message(Command("analyze"))
async def cmd_analyze(message: Message, api: BotAPIClient) -> None:
    """Trigger analytics pipeline (admin only)."""
    if not _is_admin(message):
        await message.answer("This command is restricted to administrators.")
        return

    await message.answer("<i>Starting analytics pipeline...</i>", parse_mode="HTML")
    try:
        result = await api.trigger_analytics()
        task_id = result.get("task_id", "unknown")
        status = result.get("status", "unknown")
        await message.answer(
            f"Analytics started.\n"
            f"Task ID: <code>{task_id}</code>\n"
            f"Status: <code>{status}</code>",
            parse_mode="HTML",
        )
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_analyze_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_analyze_error")
        await message.answer("Failed to trigger analytics.")


# ------------------------------------------------------------------
# /settings -- show current configuration
# ------------------------------------------------------------------


@router.message(Command("settings"))
async def cmd_settings(message: Message, api: BotAPIClient) -> None:
    """Show current system settings and configuration."""
    try:
        data = await api.get_status()
        settings = get_bot_settings()
        lines = [
            "<b>Current Settings</b>",
            "",
            f"<b>Environment:</b> <code>{data.get('environment', 'unknown')}</code>",
            f"<b>Ollama:</b> {'Enabled' if data.get('ollama', {}).get('available') else 'Disabled'}",
            f"<b>Ollama Model:</b> <code>{data.get('ollama', {}).get('model', 'N/A')}</code>",
            f"<b>Telegram Auth:</b> {'Whitelist' if settings.allowed_user_ids else 'Open'}",
            "",
            "<b>Collections:</b>",
        ]
        for run in data.get("collections", []):
            src = run.get("source_type", "?")
            status = run.get("status", "?")
            lines.append(f"  {src}: {status}")
        lines.extend([
            "",
            "<b>Database:</b>",
        ])
        db_info = data.get("database", {})
        if isinstance(db_info, dict):
            for key, val in db_info.items():
                lines.append(f"  {key}: {val}")
        text = "\n".join(lines)
        await message.answer(text, parse_mode="HTML")
    except Exception:
        logger.exception("cmd_settings_error")
        await message.answer("Failed to fetch settings.")


# ------------------------------------------------------------------
# /subscribe -- placeholder for future notification subscriptions
# ------------------------------------------------------------------


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    """Manage signal notification subscriptions (not yet implemented)."""
    await message.answer(
        "<b>Subscriptions</b>\n\n"
        "Notification subscriptions are not yet available.\n"
        "This feature will allow you to receive automatic alerts "
        "when new signals of a chosen severity are detected.",
        parse_mode="HTML",
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _is_admin(message: Message) -> bool:
    """Check whether the sender is listed in TELEGRAM_ADMIN_USERS."""
    if not message.from_user:
        return False
    settings = get_bot_settings()
    admin_ids = settings.admin_user_ids
    # If no admin list is configured, fall back to the allowed-user list
    # (i.e. every allowed user is implicitly an admin).
    if not admin_ids:
        return True
    return message.from_user.id in admin_ids


def _extract_arg(text: str | None) -> str | None:
    """Return everything after the first whitespace in a command string."""
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    return parts[1] if len(parts) > 1 else None
