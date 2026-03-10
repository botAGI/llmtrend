"""Inline keyboard builders for the Telegram bot (aiogram v3)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu keyboard shown after /start."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Quick Overview", callback_data="cmd:quick"),
        InlineKeyboardButton(text="Niches", callback_data="cmd:niches"),
    )
    builder.row(
        InlineKeyboardButton(text="Top Models", callback_data="cmd:top"),
        InlineKeyboardButton(text="Signals", callback_data="cmd:signals"),
    )
    builder.row(
        InlineKeyboardButton(text="Daily Report", callback_data="cmd:report"),
        InlineKeyboardButton(text="Status", callback_data="cmd:status"),
    )
    return builder.as_markup()


def niche_list_keyboard(niches: list[dict]) -> InlineKeyboardMarkup:
    """Build an inline keyboard with one button per niche.

    Each button carries a callback_data of ``niche:{niche_id}`` so the
    callback handler can fetch details.
    """
    builder = InlineKeyboardBuilder()
    for niche in niches[:20]:
        niche_id = niche.get("niche_id", niche.get("id", 0))
        name = str(niche.get("name", niche.get("slug", "---")))[:30]
        builder.row(
            InlineKeyboardButton(
                text=name,
                callback_data=f"niche:{niche_id}",
            )
        )
    builder.row(InlineKeyboardButton(text="<< Back", callback_data="cmd:start"))
    return builder.as_markup()


def report_type_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for choosing report type."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Daily Report", callback_data="report:daily"),
        InlineKeyboardButton(text="Weekly Report", callback_data="report:weekly"),
    )
    builder.row(InlineKeyboardButton(text="<< Back", callback_data="cmd:start"))
    return builder.as_markup()


def back_keyboard() -> InlineKeyboardMarkup:
    """Simple keyboard with a single Back button."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="<< Back", callback_data="cmd:start"))
    return builder.as_markup()


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Yes / No confirmation keyboard for admin actions.

    *action* is embedded in the callback_data so the handler knows
    what was confirmed (e.g. ``confirm:collect``).
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Yes", callback_data=f"confirm:{action}"),
        InlineKeyboardButton(text="No", callback_data="cmd:start"),
    )
    return builder.as_markup()
