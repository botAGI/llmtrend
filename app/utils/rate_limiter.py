"""Async rate limiter using a sliding-window counter backed by Redis.

Designed for distributed environments where multiple workers share rate-limit
state through a common Redis instance.  Each window is tracked by a Redis key
of the form ``ratelimit:{prefix}:{window_timestamp}``; the counter is
atomically incremented with ``INCR`` and given a TTL via ``EXPIRE``.

Typical usage::

    from redis.asyncio import Redis
    redis = Redis.from_url("redis://localhost:6379/0")
    limiter = RateLimiter(redis, key_prefix="github", max_requests=30, period_seconds=60)

    await limiter.acquire()   # blocks until a slot is available
    response = await http_client.get(...)
"""

import asyncio
import time

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Token-bucket-style rate limiter using a sliding-window counter in Redis.

    Args:
        redis: An async Redis client instance.
        key_prefix: A namespace prefix so multiple limiters can share one Redis
            instance without key collisions (e.g. ``"github"``, ``"arxiv"``).
        max_requests: Maximum number of requests allowed within a single
            *period_seconds* window.
        period_seconds: Length of the sliding window in seconds.  Defaults to
            60 (one minute).
    """

    def __init__(
        self,
        redis: Redis,
        key_prefix: str,
        max_requests: int,
        period_seconds: int = 60,
    ) -> None:
        self._redis = redis
        self._key_prefix = key_prefix
        self._max_requests = max_requests
        self._period_seconds = period_seconds

    # ── helpers ──────────────────────────────────────────────────────────

    def _current_window(self) -> int:
        """Return the timestamp that identifies the current window."""
        return int(time.time()) // self._period_seconds

    def _key_for_window(self, window: int) -> str:
        """Build the full Redis key for a given window identifier."""
        return f"ratelimit:{self._key_prefix}:{window}"

    # ── public API ───────────────────────────────────────────────────────

    async def acquire(self) -> None:
        """Wait until a request slot is available, then consume one slot.

        If the current window's counter has already reached *max_requests*,
        the coroutine sleeps until the next window opens before retrying.
        """
        while True:
            window = self._current_window()
            key = self._key_for_window(window)

            current_count = await self._redis.incr(key)

            # Ensure the key expires after the window elapses so we don't
            # leak memory.  Only set TTL on the first increment (or if TTL
            # was lost) to avoid resetting it on every call.
            if current_count == 1:
                await self._redis.expire(key, self._period_seconds * 2)

            if current_count <= self._max_requests:
                logger.debug(
                    "rate_limiter.acquired",
                    key_prefix=self._key_prefix,
                    window=window,
                    current_count=current_count,
                    max_requests=self._max_requests,
                )
                return

            # We exceeded the limit -- decrement the counter back (we won't
            # actually use this slot) and sleep until the next window.
            await self._redis.decr(key)

            elapsed_in_window = time.time() - (window * self._period_seconds)
            sleep_seconds = max(self._period_seconds - elapsed_in_window, 0.1)

            logger.warning(
                "rate_limiter.throttled",
                key_prefix=self._key_prefix,
                window=window,
                current_count=current_count - 1,
                max_requests=self._max_requests,
                sleep_seconds=round(sleep_seconds, 2),
            )

            await asyncio.sleep(sleep_seconds)

    async def is_allowed(self) -> bool:
        """Check whether a request would be allowed **without** consuming a slot.

        This is a read-only probe useful for health checks or UI indicators.

        Returns:
            ``True`` if the current window has remaining capacity, ``False``
            otherwise.
        """
        window = self._current_window()
        key = self._key_for_window(window)

        raw_value = await self._redis.get(key)
        current_count = int(raw_value) if raw_value is not None else 0

        allowed = current_count < self._max_requests
        logger.debug(
            "rate_limiter.checked",
            key_prefix=self._key_prefix,
            window=window,
            current_count=current_count,
            max_requests=self._max_requests,
            allowed=allowed,
        )
        return allowed
