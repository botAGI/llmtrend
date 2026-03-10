"""Start and help command handlers."""

from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards import main_menu_keyboard

logger = structlog.get_logger(__name__)

router = Router(name="start")

WELCOME_TEXT = """\
<b>AI Trend Monitor Bot</b>

Available commands:

<b>Reports:</b>
/report - Full daily report
/weekly - Weekly report with AI insights
/quick - Quick summary: top models + signals

<b>Data:</b>
/niches - Niche overview table
/niche &lt;name&gt; - Niche details
/top [N] - Top N models by growth (default: 10)

<b>Signals:</b>
/signals - Recent signals
/signals critical - Critical signals only

<b>Search:</b>
/search &lt;query&gt; - Search models
/model &lt;model_id&gt; - Model details

<b>AI:</b>
/ai &lt;question&gt; - Ask about trends

<b>System:</b>
/status - System status
/collect - Force data collection (admin)
/help - This message\
"""


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Send a welcome message with the list of available commands."""
    logger.info("cmd_start", user_id=message.from_user.id if message.from_user else None)
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Alias for /start -- show the command reference."""
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(lambda cb: cb.data == "cmd:start")
async def cb_start(callback: CallbackQuery) -> None:
    """Handle the 'Back' inline button by showing the main menu."""
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
