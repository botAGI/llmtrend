"""Dashboard overview API routes.

Provides aggregate statistics, top-trending items, recent signals, and
download timeline data for the frontend dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics.signals import get_recent_signals
from app.analytics.trends import get_download_timeline, get_overview_stats, get_top_trending
from app.api.schemas import (
    OverviewResponse,
    OverviewStats,
    RecentSignalItem,
    TimelineDataPoint,
    TimelineResponse,
    TrendingItem,
)
from app.dependencies import DBSession

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get(
    "/",
    response_model=OverviewResponse,
    summary="Dashboard overview",
    description="Returns total counts, top-trending items, and recent signals.",
)
async def get_overview(db: DBSession) -> OverviewResponse:
    """Dashboard overview: total counts, top trending, recent signals."""
    stats_data = await get_overview_stats(db)
    trending_data = await get_top_trending(db, limit=5)
    signals = await get_recent_signals(db, limit=5)

    stats = OverviewStats(**stats_data)

    trending = [
        TrendingItem(
            source_type=t["source_type"],
            identifier=t["identifier"],
            name=t["name"],
            metric_value=t["metric_value"],
            growth_percent=t["growth_percent"],
        )
        for t in trending_data
    ]

    recent_signals = [
        RecentSignalItem(
            id=s.id,
            signal_type=s.signal_type,
            severity=s.severity,
            source_type=s.source_type,
            source_identifier=s.source_identifier,
            description=s.description,
            detected_at=s.detected_at,
        )
        for s in signals
    ]

    return OverviewResponse(
        stats=stats,
        trending=trending,
        recent_signals=recent_signals,
    )


@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Download timeline",
    description="Download timeline data grouped by pipeline_tag for area charts.",
)
async def get_timeline(
    db: DBSession,
    pipeline_tag: str | None = Query(
        default=None,
        description="Filter by specific pipeline tag",
    ),
) -> TimelineResponse:
    """Download timeline data for area charts."""
    data = await get_download_timeline(db, pipeline_tag=pipeline_tag)

    timeline = [
        TimelineDataPoint(
            pipeline_tag=d["pipeline_tag"],
            total_downloads=d["total_downloads"],
            model_count=d["model_count"],
        )
        for d in data
    ]

    return TimelineResponse(timeline=timeline)
