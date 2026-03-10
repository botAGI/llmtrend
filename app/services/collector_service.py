"""Service layer orchestrating data collection from all external sources.

Wraps the individual collectors (:class:`HuggingFaceCollector`,
:class:`GitHubCollector`, :class:`ArxivCollector`) with session management
and structured logging.  Designed to be called from Celery tasks or ad-hoc
scripts.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors import (
    ArxivCollector,
    CollectionResult,
    GitHubCollector,
    HuggingFaceCollector,
)
from app.database import get_async_session

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Mapping from human-readable source name to collector class.
_COLLECTOR_MAP: dict[str, type] = {
    "huggingface": HuggingFaceCollector,
    "github": GitHubCollector,
    "arxiv": ArxivCollector,
}

# Ordered execution sequence -- HuggingFace first (most critical), then
# GitHub, then arXiv (most latency-tolerant).
_SOURCE_ORDER: list[str] = ["huggingface", "github", "arxiv"]


class CollectorService:
    """Orchestrates data collection from all sources.

    All methods are static and acquire their own database sessions so
    callers do not need to manage session lifecycle.
    """

    @staticmethod
    async def collect_all() -> dict[str, CollectionResult]:
        """Run all collectors sequentially.

        Sources are executed in a fixed order (HuggingFace, GitHub, arXiv).
        Each collector receives its own database session; a failure in one
        source does not prevent the remaining sources from running.

        Returns:
            A dict mapping source name to its :class:`CollectionResult`.
        """
        log.info("collector_service.collect_all.started")
        start_time = time.monotonic()

        results: dict[str, CollectionResult] = {}

        for source in _SOURCE_ORDER:
            try:
                result = await CollectorService.collect_source(source)
                results[source] = result
            except Exception as exc:
                log.error(
                    "collector_service.source_failed",
                    source=source,
                    error=str(exc),
                    exc_info=True,
                )
                # Record a failure result so the caller sees all sources.
                failure = CollectionResult()
                failure.errors.append(f"Collection aborted: {exc}")
                results[source] = failure

        elapsed = round(time.monotonic() - start_time, 2)
        total_fetched = sum(r.items_fetched for r in results.values())
        total_created = sum(r.items_created for r in results.values())
        total_updated = sum(r.items_updated for r in results.values())
        total_errors = sum(len(r.errors) for r in results.values())

        log.info(
            "collector_service.collect_all.completed",
            duration_seconds=elapsed,
            sources=len(results),
            total_fetched=total_fetched,
            total_created=total_created,
            total_updated=total_updated,
            total_errors=total_errors,
        )

        return results

    @staticmethod
    async def collect_source(source: str) -> CollectionResult:
        """Run a single collector by source name.

        Args:
            source: One of ``"huggingface"``, ``"github"``, or ``"arxiv"``.

        Returns:
            A :class:`CollectionResult` with collection statistics.

        Raises:
            ValueError: If *source* is not a recognised collector name.
        """
        source_lower = source.lower().strip()

        collector_cls = _COLLECTOR_MAP.get(source_lower)
        if collector_cls is None:
            raise ValueError(
                f"Unknown source '{source}'. "
                f"Valid sources: {', '.join(_COLLECTOR_MAP)}"
            )

        log.info("collector_service.collect_source.started", source=source_lower)
        start_time = time.monotonic()

        async for session in get_async_session():
            collector = collector_cls(session)
            result = await collector.run()

            elapsed = round(time.monotonic() - start_time, 2)
            log.info(
                "collector_service.collect_source.completed",
                source=source_lower,
                duration_seconds=elapsed,
                items_fetched=result.items_fetched,
                items_created=result.items_created,
                items_updated=result.items_updated,
                error_count=len(result.errors),
            )
            return result

        # Defensive fallback -- should not be reached because
        # get_async_session always yields exactly once.
        raise RuntimeError("Failed to acquire database session")  # pragma: no cover

    @staticmethod
    def available_sources() -> list[str]:
        """Return the list of valid source names."""
        return list(_COLLECTOR_MAP)
