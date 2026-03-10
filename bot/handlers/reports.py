"""Report-related command handlers (/quick, /report, /weekly, /top, /niches, /niche)."""

from __future__ import annotations

import io

import httpx
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.api_client import BotAPIClient
from bot.formatters import (
    format_model_list,
    format_niche_detail,
    format_niche_table,
    format_overview,
    format_report_preview,
    truncate_for_telegram,
)
from bot.keyboards import back_keyboard, niche_list_keyboard

logger = structlog.get_logger(__name__)

router = Router(name="reports")


# ------------------------------------------------------------------
# /quick
# ------------------------------------------------------------------


@router.message(Command("quick"))
async def cmd_quick(message: Message, api: BotAPIClient) -> None:
    """Quick overview: top growing models and recent signals."""
    await message.answer("<i>Loading overview...</i>", parse_mode="HTML")
    try:
        data = await api.get_overview()
        text = format_overview(data)
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_quick_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_quick_error")
        await message.answer("Failed to fetch overview. Try again later.")


@router.callback_query(lambda cb: cb.data == "cmd:quick")
async def cb_quick(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle inline button for quick overview."""
    await callback.answer()
    try:
        data = await api.get_overview()
        text = format_overview(data)
        if callback.message:
            await callback.message.edit_text(
                text, parse_mode="HTML", reply_markup=back_keyboard()
            )
    except Exception:
        logger.exception("cb_quick_error")
        if callback.message:
            await callback.message.edit_text("Failed to fetch overview.")


# ------------------------------------------------------------------
# /report
# ------------------------------------------------------------------


@router.message(Command("report"))
async def cmd_report(message: Message, api: BotAPIClient) -> None:
    """Generate and send a daily report."""
    await message.answer("<i>Generating daily report -- this may take a moment...</i>", parse_mode="HTML")
    try:
        report = await api.generate_report("daily")
        await _send_report(message, report)
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_report_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_report_error")
        await message.answer("Failed to generate report. Try again later.")


@router.callback_query(lambda cb: cb.data == "cmd:report")
async def cb_report(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle inline button for daily report."""
    await callback.answer("Generating report...")
    try:
        report = await api.generate_report("daily")
        if callback.message:
            await _send_report(callback.message, report)
    except Exception:
        logger.exception("cb_report_error")
        if callback.message:
            await callback.message.answer("Failed to generate report.")


@router.callback_query(lambda cb: cb.data and cb.data.startswith("report:"))
async def cb_report_type(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle report type selection from keyboard."""
    await callback.answer("Generating report...")
    report_type = str(callback.data).split(":", 1)[1]
    try:
        report = await api.generate_report(report_type)
        if callback.message:
            await _send_report(callback.message, report)
    except Exception:
        logger.exception("cb_report_type_error", report_type=report_type)
        if callback.message:
            await callback.message.answer("Failed to generate report.")


# ------------------------------------------------------------------
# /weekly
# ------------------------------------------------------------------


@router.message(Command("weekly"))
async def cmd_weekly(message: Message, api: BotAPIClient) -> None:
    """Generate and send a weekly report."""
    await message.answer("<i>Generating weekly report -- this may take a moment...</i>", parse_mode="HTML")
    try:
        report = await api.generate_report("weekly")
        await _send_report(message, report)
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_weekly_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_weekly_error")
        await message.answer("Failed to generate weekly report. Try again later.")


# ------------------------------------------------------------------
# /top [N]
# ------------------------------------------------------------------


@router.message(Command("top"))
async def cmd_top(message: Message, api: BotAPIClient) -> None:
    """Show top N models by growth (default 10)."""
    limit = _parse_int_arg(message.text, default=10, maximum=50)
    try:
        models = await api.get_top_models(limit=limit)
        text = format_model_list(models, title=f"Top {limit} Models by Growth")
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_top_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_top_error")
        await message.answer("Failed to fetch top models.")


@router.callback_query(lambda cb: cb.data == "cmd:top")
async def cb_top(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle inline button for top models."""
    await callback.answer()
    try:
        models = await api.get_top_models(limit=10)
        text = format_model_list(models, title="Top 10 Models by Growth")
        if callback.message:
            await callback.message.edit_text(
                text, parse_mode="HTML", reply_markup=back_keyboard()
            )
    except Exception:
        logger.exception("cb_top_error")
        if callback.message:
            await callback.message.edit_text("Failed to fetch top models.")


# ------------------------------------------------------------------
# /niches
# ------------------------------------------------------------------


@router.message(Command("niches"))
async def cmd_niches(message: Message, api: BotAPIClient) -> None:
    """Show niche overview table."""
    try:
        niches = await api.get_niches()
        text = format_niche_table(niches)
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=niche_list_keyboard(niches),
        )
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_niches_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_niches_error")
        await message.answer("Failed to fetch niches.")


@router.callback_query(lambda cb: cb.data == "cmd:niches")
async def cb_niches(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle inline button for niches."""
    await callback.answer()
    try:
        niches = await api.get_niches()
        text = format_niche_table(niches)
        if callback.message:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=niche_list_keyboard(niches),
            )
    except Exception:
        logger.exception("cb_niches_error")
        if callback.message:
            await callback.message.edit_text("Failed to fetch niches.")


# ------------------------------------------------------------------
# /niche <name_or_id>
# ------------------------------------------------------------------


@router.message(Command("niche"))
async def cmd_niche(message: Message, api: BotAPIClient) -> None:
    """Show detailed information for a specific niche."""
    arg = _extract_arg(message.text)
    if not arg:
        await message.answer("Usage: /niche &lt;name or id&gt;", parse_mode="HTML")
        return

    # If the argument looks numeric, treat it as a niche_id directly.
    if arg.isdigit():
        niche_id = int(arg)
    else:
        # Look up the niche by name/slug in the full list.
        niches = await api.get_niches()
        match = _find_niche_by_name(niches, arg)
        if match is None:
            await message.answer(f"Niche <code>{arg}</code> not found.", parse_mode="HTML")
            return
        niche_id = match.get("niche_id", match.get("id", 0))

    try:
        niche = await api.get_niche_detail(niche_id)
        text = format_niche_detail(niche)
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await message.answer("Niche not found.")
        else:
            await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_niche_error")
        await message.answer("Failed to fetch niche details.")


@router.callback_query(lambda cb: cb.data and cb.data.startswith("niche:"))
async def cb_niche_detail(callback: CallbackQuery, api: BotAPIClient) -> None:
    """Handle niche selection from the inline keyboard."""
    await callback.answer()
    niche_id_str = str(callback.data).split(":", 1)[1]
    try:
        niche_id = int(niche_id_str)
        niche = await api.get_niche_detail(niche_id)
        text = format_niche_detail(niche)
        if callback.message:
            await callback.message.edit_text(
                text, parse_mode="HTML", reply_markup=back_keyboard()
            )
    except Exception:
        logger.exception("cb_niche_detail_error", niche_id=niche_id_str)
        if callback.message:
            await callback.message.edit_text("Failed to fetch niche details.")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


async def _send_report(message: Message, report: dict) -> None:
    """Send report as text or as a .md document if it exceeds Telegram limits."""
    content = report.get("content_markdown", "")
    title = report.get("title", report.get("report_type", "report"))

    if not content:
        preview = format_report_preview(report)
        await message.answer(preview, parse_mode="HTML", reply_markup=back_keyboard())
        return

    # If the rendered preview fits, send inline.
    preview = format_report_preview(report)
    if len(preview) <= 4096:
        await message.answer(preview, parse_mode="HTML", reply_markup=back_keyboard())
        return

    # Otherwise send as a .md file attachment.
    file_bytes = content.encode("utf-8")
    filename = f"{title.lower().replace(' ', '_')}.md"
    doc = BufferedInputFile(file=file_bytes, filename=filename)
    await message.answer_document(
        document=doc,
        caption=truncate_for_telegram(f"<b>{title}</b>", max_length=1024),
        parse_mode="HTML",
    )


def _parse_int_arg(text: str | None, default: int = 10, maximum: int = 50) -> int:
    """Extract a single integer argument from a command string like '/top 20'."""
    if not text:
        return default
    parts = text.strip().split()
    if len(parts) >= 2:
        try:
            value = int(parts[1])
            return min(max(value, 1), maximum)
        except ValueError:
            pass
    return default


def _extract_arg(text: str | None) -> str | None:
    """Return everything after the first space in a command string."""
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    return parts[1] if len(parts) > 1 else None


def _find_niche_by_name(niches: list[dict], query: str) -> dict | None:
    """Find a niche whose name or slug matches *query* (case-insensitive)."""
    q = query.lower()
    for n in niches:
        name = str(n.get("name", "")).lower()
        slug = str(n.get("slug", "")).lower()
        if q == name or q == slug or q in name:
            return n
    return None
