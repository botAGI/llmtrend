"""Celery tasks for data collection.

Wraps :class:`CollectorService` methods as Celery tasks.  Since the
collectors are async, each task bridges the sync/async boundary with
:func:`asyncio.run`.  Imports are deferred inside the async helpers to
avoid circular imports and to ensure the event loop is created cleanly.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.tasks.celery_app import celery_app

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ======================================================================
# Collect all sources
# ======================================================================


@celery_app.task(
    name="app.tasks.collection_tasks.collect_all_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def collect_all_task(self: Any) -> dict[str, dict[str, int]]:
    """Celery task to run all collectors.

    Retries up to 2 times on failure with a 60-second delay between
    attempts.

    Returns:
        A dict mapping source name to a summary dict with ``fetched``,
        ``created``, ``updated``, and ``errors`` counts.
    """
    log.info("celery.collect_all_task.started", task_id=self.request.id)

    try:
        result = asyncio.run(_collect_all())
        log.info("celery.collect_all_task.completed", task_id=self.request.id)
        return result
    except Exception as exc:
        log.error(
            "celery.collect_all_task.failed",
            task_id=self.request.id,
            error=str(exc),
            retries=self.request.retries,
            exc_info=True,
        )
        raise self.retry(exc=exc)


async def _collect_all() -> dict[str, dict[str, int]]:
    """Async implementation for :func:`collect_all_task`."""
    from app.services.collector_service import CollectorService

    results = await CollectorService.collect_all()

    return {
        source: {
            "fetched": r.items_fetched,
            "created": r.items_created,
            "updated": r.items_updated,
            "errors": len(r.errors),
        }
        for source, r in results.items()
    }


# ======================================================================
# Collect single source
# ======================================================================


@celery_app.task(
    name="app.tasks.collection_tasks.collect_source_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def collect_source_task(self: Any, source: str) -> dict[str, int]:
    """Celery task to run a single collector.

    Args:
        source: The source name (``"huggingface"``, ``"github"``, or
                ``"arxiv"``).

    Returns:
        A summary dict with ``fetched``, ``created``, ``updated``, and
        ``errors`` counts.
    """
    log.info(
        "celery.collect_source_task.started",
        task_id=self.request.id,
        source=source,
    )

    try:
        result = asyncio.run(_collect_source(source))
        log.info(
            "celery.collect_source_task.completed",
            task_id=self.request.id,
            source=source,
        )
        return result
    except Exception as exc:
        log.error(
            "celery.collect_source_task.failed",
            task_id=self.request.id,
            source=source,
            error=str(exc),
            retries=self.request.retries,
            exc_info=True,
        )
        raise self.retry(exc=exc)


async def _collect_source(source: str) -> dict[str, int]:
    """Async implementation for :func:`collect_source_task`."""
    from app.services.collector_service import CollectorService

    result = await CollectorService.collect_source(source)

    return {
        "fetched": result.items_fetched,
        "created": result.items_created,
        "updated": result.items_updated,
        "errors": len(result.errors),
    }
