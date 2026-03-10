"""Signal detection -- identifies anomalies and notable events in tracked data.

Monitors HuggingFace model downloads, GitHub repo stars, and new high-traction
entries, creating :class:`TrendSignal` rows when thresholds are exceeded.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_repo import GitHubRepo
from app.models.hf_model import HFModel
from app.models.trend_signal import TrendSignal
from app.utils.helpers import utc_now

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Threshold configuration
# ---------------------------------------------------------------------------

SIGNAL_THRESHOLDS: dict[str, dict[str, int]] = {
    "download_spike": {"medium": 50, "high": 100, "critical": 200},
    "star_spike": {"medium": 30, "high": 75, "critical": 150},
    "new_entry": {"medium": 0},
    "paper_surge": {"medium": 20, "high": 50, "critical": 100},
}


def _determine_severity(signal_type: str, value: float) -> str | None:
    """Return the severity level for a given signal type and observed value.

    Thresholds are checked from most severe to least severe so the highest
    applicable level is returned.  Returns ``None`` if no threshold is met.
    """
    thresholds = SIGNAL_THRESHOLDS.get(signal_type)
    if thresholds is None:
        return None

    for level in ("critical", "high", "medium"):
        if level in thresholds and value >= thresholds[level]:
            return level
    return None


# ---------------------------------------------------------------------------
# Duplicate guard
# ---------------------------------------------------------------------------


async def _signal_exists_recently(
    session: AsyncSession,
    source_type: str,
    source_id: int,
    signal_type: str,
    hours: int = 24,
) -> bool:
    """Check whether a signal of the same kind already exists within *hours*."""
    cutoff = utc_now() - timedelta(hours=hours)
    stmt = select(func.count(TrendSignal.id)).where(
        and_(
            TrendSignal.source_type == source_type,
            TrendSignal.source_id == source_id,
            TrendSignal.signal_type == signal_type,
            TrendSignal.detected_at >= cutoff,
        )
    )
    count: int = (await session.execute(stmt)).scalar_one()
    return count > 0


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------


async def generate_signals(session: AsyncSession) -> list[TrendSignal]:
    """Detect anomalies in current data and persist new :class:`TrendSignal` rows.

    Detection rules
    ~~~~~~~~~~~~~~~~
    1. **Download spikes** -- HF models whose download growth percentage
       exceeds the ``download_spike`` thresholds.
    2. **Star spikes** -- GitHub repos whose star growth percentage exceeds
       the ``star_spike`` thresholds.
    3. **New high-traction entries** -- HF models first seen in the last 7 days
       that already have more than 10 000 downloads.

    Duplicate signals (same source + type within 24 h) are suppressed.

    Returns:
        The list of newly created :class:`TrendSignal` instances (already
        added to the session but not yet committed).
    """

    log.info("generating_signals")
    now = utc_now()
    created_signals: list[TrendSignal] = []

    # -- 1. HF download spikes ----------------------------------------------

    hf_stmt = select(HFModel).where(HFModel.downloads_previous > 0)
    hf_result = await session.execute(hf_stmt)
    hf_models: list[HFModel] = list(hf_result.scalars().all())

    for model in hf_models:
        growth_pct = (
            (model.downloads - model.downloads_previous)
            / model.downloads_previous
            * 100.0
        )
        severity = _determine_severity("download_spike", growth_pct)
        if severity is None:
            continue

        if await _signal_exists_recently(
            session, "hf_model", model.id, "download_spike"
        ):
            continue

        delta = model.downloads - model.downloads_previous
        signal = TrendSignal(
            source_type="hf_model",
            source_id=model.id,
            source_identifier=model.model_id,
            signal_type="download_spike",
            severity=severity,
            value=float(model.downloads),
            delta=float(delta),
            delta_percent=round(growth_pct, 2),
            description=(
                f"Download spike detected for {model.model_id}: "
                f"{model.downloads_previous:,} -> {model.downloads:,} "
                f"({growth_pct:+.1f}%)"
            ),
            metadata_json={
                "pipeline_tag": model.pipeline_tag,
                "author": model.author,
                "previous": model.downloads_previous,
                "current": model.downloads,
            },
            detected_at=now,
        )
        session.add(signal)
        created_signals.append(signal)

    # -- 2. GitHub star spikes -----------------------------------------------

    gh_stmt = select(GitHubRepo).where(GitHubRepo.stars_previous > 0)
    gh_result = await session.execute(gh_stmt)
    gh_repos: list[GitHubRepo] = list(gh_result.scalars().all())

    for repo in gh_repos:
        growth_pct = (
            (repo.stars - repo.stars_previous)
            / repo.stars_previous
            * 100.0
        )
        severity = _determine_severity("star_spike", growth_pct)
        if severity is None:
            continue

        if await _signal_exists_recently(
            session, "github_repo", repo.id, "star_spike"
        ):
            continue

        delta = repo.stars - repo.stars_previous
        signal = TrendSignal(
            source_type="github_repo",
            source_id=repo.id,
            source_identifier=repo.full_name,
            signal_type="star_spike",
            severity=severity,
            value=float(repo.stars),
            delta=float(delta),
            delta_percent=round(growth_pct, 2),
            description=(
                f"Star spike detected for {repo.full_name}: "
                f"{repo.stars_previous:,} -> {repo.stars:,} "
                f"({growth_pct:+.1f}%)"
            ),
            metadata_json={
                "language": repo.language,
                "owner": repo.owner_login,
                "previous": repo.stars_previous,
                "current": repo.stars,
            },
            detected_at=now,
        )
        session.add(signal)
        created_signals.append(signal)

    # -- 3. New high-traction entries ----------------------------------------

    seven_days_ago = now - timedelta(days=7)
    new_stmt = select(HFModel).where(
        and_(
            HFModel.first_seen_at >= seven_days_ago,
            HFModel.downloads > 10_000,
        )
    )
    new_result = await session.execute(new_stmt)
    new_models: list[HFModel] = list(new_result.scalars().all())

    for model in new_models:
        if await _signal_exists_recently(
            session, "hf_model", model.id, "new_entry"
        ):
            continue

        signal = TrendSignal(
            source_type="hf_model",
            source_id=model.id,
            source_identifier=model.model_id,
            signal_type="new_entry",
            severity="medium",
            value=float(model.downloads),
            delta=None,
            delta_percent=None,
            description=(
                f"New high-traction model detected: {model.model_id} "
                f"with {model.downloads:,} downloads in its first week"
            ),
            metadata_json={
                "pipeline_tag": model.pipeline_tag,
                "author": model.author,
                "first_seen_at": model.first_seen_at.isoformat(),
                "downloads": model.downloads,
            },
            detected_at=now,
        )
        session.add(signal)
        created_signals.append(signal)

    await session.flush()

    log.info(
        "signals_generated",
        total=len(created_signals),
        download_spikes=sum(
            1 for s in created_signals if s.signal_type == "download_spike"
        ),
        star_spikes=sum(
            1 for s in created_signals if s.signal_type == "star_spike"
        ),
        new_entries=sum(
            1 for s in created_signals if s.signal_type == "new_entry"
        ),
    )

    return created_signals


# ---------------------------------------------------------------------------
# Querying signals
# ---------------------------------------------------------------------------


async def get_recent_signals(
    session: AsyncSession,
    limit: int = 10,
    severity: str | None = None,
    signal_type: str | None = None,
) -> list[TrendSignal]:
    """Retrieve the most recent trend signals with optional filtering.

    Args:
        session: An active async database session.
        limit: Maximum number of signals to return.
        severity: Filter by severity level (``"medium"``, ``"high"``,
                  ``"critical"``).
        signal_type: Filter by signal type (``"download_spike"``,
                     ``"star_spike"``, ``"new_entry"``, ``"paper_surge"``).

    Returns:
        A list of :class:`TrendSignal` instances ordered by ``detected_at``
        descending.
    """

    log.debug("fetching_recent_signals", limit=limit, severity=severity, signal_type=signal_type)

    stmt = select(TrendSignal).order_by(TrendSignal.detected_at.desc())

    if severity is not None:
        stmt = stmt.where(TrendSignal.severity == severity)
    if signal_type is not None:
        stmt = stmt.where(TrendSignal.signal_type == signal_type)

    stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Signal statistics
# ---------------------------------------------------------------------------


async def get_signal_stats(session: AsyncSession) -> dict[str, Any]:
    """Count signals grouped by time period.

    Returns:
        A dict with keys ``today``, ``this_week``, ``this_month``, each
        containing the count of signals detected in that period, plus
        ``by_severity`` and ``by_type`` breakdowns for the current month.
    """

    log.debug("computing_signal_stats")
    now = utc_now()

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    today_count: int = (
        await session.execute(
            select(func.count(TrendSignal.id)).where(
                TrendSignal.detected_at >= today_start
            )
        )
    ).scalar_one()

    week_count: int = (
        await session.execute(
            select(func.count(TrendSignal.id)).where(
                TrendSignal.detected_at >= week_start
            )
        )
    ).scalar_one()

    month_count: int = (
        await session.execute(
            select(func.count(TrendSignal.id)).where(
                TrendSignal.detected_at >= month_start
            )
        )
    ).scalar_one()

    # Breakdown by severity (this month)
    severity_stmt = (
        select(TrendSignal.severity, func.count(TrendSignal.id))
        .where(TrendSignal.detected_at >= month_start)
        .group_by(TrendSignal.severity)
    )
    severity_result = await session.execute(severity_stmt)
    by_severity: dict[str, int] = {
        row[0]: row[1] for row in severity_result.all()
    }

    # Breakdown by type (this month)
    type_stmt = (
        select(TrendSignal.signal_type, func.count(TrendSignal.id))
        .where(TrendSignal.detected_at >= month_start)
        .group_by(TrendSignal.signal_type)
    )
    type_result = await session.execute(type_stmt)
    by_type: dict[str, int] = {row[0]: row[1] for row in type_result.all()}

    return {
        "today": today_count,
        "this_week": week_count,
        "this_month": month_count,
        "by_severity": by_severity,
        "by_type": by_type,
    }
