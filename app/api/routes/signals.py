"""Trend signal API routes.

Provides listing with filtering, statistics, and read-status management
for detected trend signals.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.signals import get_recent_signals, get_signal_stats
from app.api.schemas import (
    SignalItem,
    SignalListResponse,
    SignalReadResponse,
    SignalStatsResponse,
)
from app.dependencies import DBSession
from app.models.trend_signal import TrendSignal

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get(
    "/",
    response_model=SignalListResponse,
    summary="List signals",
    description="List trend signals with optional filtering by severity, type, and source.",
)
async def list_signals(
    db: DBSession,
    severity: str | None = Query(
        default=None,
        description="Filter by severity: medium, high, critical",
    ),
    signal_type: str | None = Query(
        default=None,
        description="Filter by type: download_spike, star_spike, new_entry, paper_surge",
    ),
    source_type: str | None = Query(
        default=None,
        description="Filter by source: hf_model, github_repo",
    ),
    limit: int = Query(default=20, ge=1, le=200, description="Max items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
) -> SignalListResponse:
    """List signals with filtering."""
    # -- Count query --------------------------------------------------------
    count_stmt = select(func.count(TrendSignal.id))

    if severity is not None:
        count_stmt = count_stmt.where(TrendSignal.severity == severity)
    if signal_type is not None:
        count_stmt = count_stmt.where(TrendSignal.signal_type == signal_type)
    if source_type is not None:
        count_stmt = count_stmt.where(TrendSignal.source_type == source_type)

    total: int = (await db.execute(count_stmt)).scalar_one()

    # -- Data query ---------------------------------------------------------
    signals = await get_recent_signals(
        db,
        limit=limit + offset,  # fetch enough to account for offset
        severity=severity,
        signal_type=signal_type,
    )

    # get_recent_signals does not support source_type or offset natively,
    # so we apply those manually here for maximum flexibility.
    if source_type is not None:
        signals = [s for s in signals if s.source_type == source_type]

    # Apply offset/limit after filtering
    paginated = signals[offset : offset + limit]

    items = [
        SignalItem(
            id=s.id,
            source_type=s.source_type,
            source_id=s.source_id,
            source_identifier=s.source_identifier,
            signal_type=s.signal_type,
            severity=s.severity,
            value=s.value,
            delta=s.delta,
            delta_percent=s.delta_percent,
            description=s.description,
            metadata_json=s.metadata_json or {},
            niche_id=s.niche_id,
            detected_at=s.detected_at,
            is_read=s.is_read,
            created_at=s.created_at,
        )
        for s in paginated
    ]

    return SignalListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/stats",
    response_model=SignalStatsResponse,
    summary="Signal statistics",
    description="Signal counts grouped by time period, severity, and type.",
)
async def signal_stats(db: DBSession) -> SignalStatsResponse:
    """Get signal counts by period and type."""
    stats = await get_signal_stats(db)

    return SignalStatsResponse(
        today=stats["today"],
        this_week=stats["this_week"],
        this_month=stats["this_month"],
        by_severity=stats["by_severity"],
        by_type=stats["by_type"],
    )


@router.patch(
    "/{signal_id}/read",
    response_model=SignalReadResponse,
    summary="Mark signal as read",
    description="Mark a specific signal as read by its ID.",
)
async def mark_signal_read(signal_id: int, db: DBSession) -> SignalReadResponse:
    """Mark a signal as read."""
    stmt = select(TrendSignal).where(TrendSignal.id == signal_id)
    result = await db.execute(stmt)
    signal = result.scalar_one_or_none()

    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal with id={signal_id} not found",
        )

    signal.is_read = True
    await db.flush()

    return SignalReadResponse(id=signal.id, is_read=True)
