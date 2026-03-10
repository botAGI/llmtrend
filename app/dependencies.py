"""FastAPI dependency injection functions."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_async_session

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    async for session in get_async_session():
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]

_redis_client: Redis | None = None


async def get_redis(settings: SettingsDep) -> Redis:
    """Provide a Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


RedisDep = Annotated[Redis, Depends(get_redis)]


async def verify_api_key(
    settings: SettingsDep,
    x_api_key: str | None = Header(default=None),
) -> None:
    """Verify API key if configured."""
    if not settings.APP_API_KEY:
        return
    if x_api_key != settings.APP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
