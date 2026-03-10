"""Search, model detail, and AI question handlers (/search, /model, /ai)."""

from __future__ import annotations

import httpx
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.api_client import BotAPIClient
from bot.formatters import format_model_card, format_model_list
from bot.keyboards import back_keyboard

logger = structlog.get_logger(__name__)

router = Router(name="search")


# ------------------------------------------------------------------
# /search <query>
# ------------------------------------------------------------------


@router.message(Command("search"))
async def cmd_search(message: Message, api: BotAPIClient) -> None:
    """Search models by name, tag, or keyword.

    Usage: /search text-generation
    """
    query = _extract_arg(message.text)
    if not query:
        await message.answer(
            "Usage: /search &lt;query&gt;\nExample: /search text-generation",
            parse_mode="HTML",
        )
        return

    try:
        models = await api.search_models(query=query, limit=10)
        if not models:
            await message.answer(
                f"No models found for <code>{_escape(query)}</code>.",
                parse_mode="HTML",
            )
            return
        text = format_model_list(models, title=f"Search: {query}")
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_search_http_error", status=exc.response.status_code)
        await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_search_error")
        await message.answer("Search failed. Try again later.")


# ------------------------------------------------------------------
# /model <model_id>
# ------------------------------------------------------------------


@router.message(Command("model"))
async def cmd_model(message: Message, api: BotAPIClient) -> None:
    """Show detailed information for a specific model.

    Usage: /model meta-llama/Llama-2-7b
    """
    model_id = _extract_arg(message.text)
    if not model_id:
        await message.answer(
            "Usage: /model &lt;model_id&gt;\nExample: /model meta-llama/Llama-2-7b",
            parse_mode="HTML",
        )
        return

    try:
        model = await api.get_model(model_id.strip())
        text = format_model_card(model)
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await message.answer(
                f"Model <code>{_escape(model_id)}</code> not found.",
                parse_mode="HTML",
            )
        else:
            logger.error("cmd_model_http_error", status=exc.response.status_code)
            await message.answer(f"API error: {exc.response.status_code}")
    except Exception:
        logger.exception("cmd_model_error")
        await message.answer("Failed to fetch model details.")


# ------------------------------------------------------------------
# /ai <question>
# ------------------------------------------------------------------


@router.message(Command("ai"))
async def cmd_ai(message: Message, api: BotAPIClient) -> None:
    """Ask an AI-powered question about current trends.

    This generates a report-style answer by calling the backend's
    report generation endpoint with a custom prompt.

    Usage: /ai What are the fastest growing text generation models?
    """
    question = _extract_arg(message.text)
    if not question:
        await message.answer(
            "Usage: /ai &lt;question&gt;\n"
            "Example: /ai What are the fastest growing text generation models?",
            parse_mode="HTML",
        )
        return

    await message.answer(
        "<i>Thinking...</i>",
        parse_mode="HTML",
    )

    try:
        # Use the report generation endpoint; the backend interprets
        # the report_type as a free-form query when it does not match
        # a known template.
        report = await api.generate_report(report_type=f"ai_query:{question}")
        content = report.get("content_markdown", "")
        if content:
            from html import escape as html_escape

            text = f"<b>AI Analysis</b>\n\n{html_escape(content)}"
        else:
            text = "<i>No analysis available for this query.</i>"
        from bot.formatters import truncate_for_telegram

        text = truncate_for_telegram(text)
        await message.answer(text, parse_mode="HTML", reply_markup=back_keyboard())
    except httpx.HTTPStatusError as exc:
        logger.error("cmd_ai_http_error", status=exc.response.status_code)
        await message.answer(
            "AI analysis is currently unavailable. "
            f"(HTTP {exc.response.status_code})"
        )
    except Exception:
        logger.exception("cmd_ai_error")
        await message.answer("AI analysis failed. Try again later.")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_arg(text: str | None) -> str | None:
    """Return everything after the first whitespace in a command string."""
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    return parts[1] if len(parts) > 1 else None


def _escape(text: str) -> str:
    """HTML-escape a string for safe embedding in Telegram messages."""
    from html import escape

    return escape(text)
