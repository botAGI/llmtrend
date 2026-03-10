"""aiogram v3 middleware for authentication and access control."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import structlog
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = structlog.get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Restrict bot access to a whitelist of Telegram user IDs.

    If ``allowed_user_ids`` is empty the middleware lets every message
    through (open access mode).  Otherwise only messages from users
    whose ``from_user.id`` appears in the whitelist are forwarded to
    the handler; everyone else receives an "Access denied" reply.
    """

    def __init__(self, allowed_user_ids: list[int]) -> None:
        self.allowed_user_ids: list[int] = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # If no whitelist is configured, allow everyone.
        if not self.allowed_user_ids:
            return await handler(event, data)

        # Only gate Message events that carry a from_user.
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            if user_id not in self.allowed_user_ids:
                logger.warning(
                    "access_denied",
                    user_id=user_id,
                    username=event.from_user.username,
                )
                await event.answer("Access denied. You are not authorised to use this bot.")
                return None

        return await handler(event, data)
