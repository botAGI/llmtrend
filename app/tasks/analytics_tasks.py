"""Celery tasks for analytics and report generation.

Wraps analytics functions and :class:`ReportGenerator` methods as Celery
tasks.  All heavy lifting is async; :func:`asyncio.run` bridges the
sync/async boundary.  Imports are deferred inside async helpers to avoid
circular imports and to keep event-loop creation clean.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.tasks.celery_app import celery_app

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ======================================================================
# Run analytics pipeline
# ======================================================================


@celery_app.task(
    name="app.tasks.analytics_tasks.run_analytics_task",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def run_analytics_task(self: Any) -> dict[str, Any]:
    """Run the full analytics pipeline: growth rates, signal detection,
    niche assignment, and default niche seeding.

    Returns:
        A summary dict with ``signals_created``, ``niche_assignments``,
        and ``growth_models``/``growth_repos`` counts.
    """
    log.info("celery.run_analytics_task.started", task_id=self.request.id)

    try:
        result = asyncio.run(_run_analytics())
        log.info(
            "celery.run_analytics_task.completed",
            task_id=self.request.id,
            **result,
        )
        return result
    except Exception as exc:
        log.error(
            "celery.run_analytics_task.failed",
            task_id=self.request.id,
            error=str(exc),
            retries=self.request.retries,
            exc_info=True,
        )
        raise self.retry(exc=exc)


async def _run_analytics() -> dict[str, Any]:
    """Async implementation for :func:`run_analytics_task`."""
    from app.analytics.niches import assign_models_to_niches, ensure_default_niches
    from app.analytics.signals import generate_signals
    from app.analytics.trends import compute_growth_rates
    from app.database import get_async_session

    async for session in get_async_session():
        # Ensure default niches exist before assignment.
        await ensure_default_niches(session)

        # Compute growth rates (updates are in-place via the session).
        growth = await compute_growth_rates(session)

        # Detect anomalies and create signal rows.
        signals = await generate_signals(session)

        # Assign models/repos to niches based on keyword matching.
        new_assignments = await assign_models_to_niches(session)

        return {
            "growth_models": len(growth.get("hf_models", [])),
            "growth_repos": len(growth.get("github_repos", [])),
            "signals_created": len(signals),
            "niche_assignments": new_assignments,
        }

    # Defensive fallback.
    raise RuntimeError("Failed to acquire database session")  # pragma: no cover


# ======================================================================
# Generate daily report
# ======================================================================


@celery_app.task(
    name="app.tasks.analytics_tasks.generate_daily_report_task",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    acks_late=True,
)
def generate_daily_report_task(self: Any) -> dict[str, Any]:
    """Generate and persist a daily summary report.

    Returns:
        A dict with ``report_id``, ``report_type``, and ``file_path``.
    """
    log.info("celery.generate_daily_report_task.started", task_id=self.request.id)

    try:
        result = asyncio.run(_generate_daily_report())
        log.info(
            "celery.generate_daily_report_task.completed",
            task_id=self.request.id,
            **result,
        )
        return result
    except Exception as exc:
        log.error(
            "celery.generate_daily_report_task.failed",
            task_id=self.request.id,
            error=str(exc),
            retries=self.request.retries,
            exc_info=True,
        )
        raise self.retry(exc=exc)


async def _generate_daily_report() -> dict[str, Any]:
    """Async implementation for :func:`generate_daily_report_task`."""
    from app.database import get_async_session
    from app.services.report_generator import ReportGenerator

    async for session in get_async_session():
        report = await ReportGenerator.generate_daily_report(session)
        return {
            "report_id": report.id,
            "report_type": report.report_type,
            "title": report.title,
            "file_path": report.file_path,
            "generation_time_seconds": report.generation_time_seconds,
        }

    raise RuntimeError("Failed to acquire database session")  # pragma: no cover


# ======================================================================
# Generate weekly report
# ======================================================================


@celery_app.task(
    name="app.tasks.analytics_tasks.generate_weekly_report_task",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    acks_late=True,
)
def generate_weekly_report_task(self: Any) -> dict[str, Any]:
    """Generate and persist a weekly summary report with AI insights.

    Returns:
        A dict with ``report_id``, ``report_type``, and ``file_path``.
    """
    log.info("celery.generate_weekly_report_task.started", task_id=self.request.id)

    try:
        result = asyncio.run(_generate_weekly_report())
        log.info(
            "celery.generate_weekly_report_task.completed",
            task_id=self.request.id,
            **result,
        )
        return result
    except Exception as exc:
        log.error(
            "celery.generate_weekly_report_task.failed",
            task_id=self.request.id,
            error=str(exc),
            retries=self.request.retries,
            exc_info=True,
        )
        raise self.retry(exc=exc)


async def _generate_weekly_report() -> dict[str, Any]:
    """Async implementation for :func:`generate_weekly_report_task`."""
    from app.database import get_async_session
    from app.services.report_generator import ReportGenerator

    async for session in get_async_session():
        report = await ReportGenerator.generate_weekly_report(session)
        return {
            "report_id": report.id,
            "report_type": report.report_type,
            "title": report.title,
            "file_path": report.file_path,
            "generation_time_seconds": report.generation_time_seconds,
        }

    raise RuntimeError("Failed to acquire database session")  # pragma: no cover


# ======================================================================
# Generate niche report (on-demand)
# ======================================================================


@celery_app.task(
    name="app.tasks.analytics_tasks.generate_niche_report_task",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
    acks_late=True,
)
def generate_niche_report_task(self: Any, niche_id: int) -> dict[str, Any]:
    """Generate and persist a deep-dive report for a specific niche.

    Args:
        niche_id: Primary key of the target niche.

    Returns:
        A dict with ``report_id``, ``report_type``, ``niche_id``, and
        ``file_path``.
    """
    log.info(
        "celery.generate_niche_report_task.started",
        task_id=self.request.id,
        niche_id=niche_id,
    )

    try:
        result = asyncio.run(_generate_niche_report(niche_id))
        log.info(
            "celery.generate_niche_report_task.completed",
            task_id=self.request.id,
            niche_id=niche_id,
            **result,
        )
        return result
    except Exception as exc:
        log.error(
            "celery.generate_niche_report_task.failed",
            task_id=self.request.id,
            niche_id=niche_id,
            error=str(exc),
            retries=self.request.retries,
            exc_info=True,
        )
        raise self.retry(exc=exc)


async def _generate_niche_report(niche_id: int) -> dict[str, Any]:
    """Async implementation for :func:`generate_niche_report_task`."""
    from app.database import get_async_session
    from app.services.report_generator import ReportGenerator

    async for session in get_async_session():
        report = await ReportGenerator.generate_niche_report(session, niche_id)
        return {
            "report_id": report.id,
            "report_type": report.report_type,
            "niche_id": niche_id,
            "title": report.title,
            "file_path": report.file_path,
            "generation_time_seconds": report.generation_time_seconds,
        }

    raise RuntimeError("Failed to acquire database session")  # pragma: no cover
