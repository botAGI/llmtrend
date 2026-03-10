"""Trend detection and growth-rate computation for the AI Trend Monitor.

Provides functions to compute growth rates across HuggingFace models and GitHub
repositories, surface top-trending items, and produce dashboard overview stats.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arxiv_paper import ArxivPaper
from app.models.github_repo import GitHubRepo
from app.models.hf_model import HFModel
from app.models.niche import Niche
from app.models.trend_signal import TrendSignal

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Growth rates
# ---------------------------------------------------------------------------


async def compute_growth_rates(
    session: AsyncSession,
    days: int = 7,
) -> dict[str, list[dict[str, Any]]]:
    """Compute growth rates for HuggingFace models and GitHub repositories.

    Only items with a positive ``_previous`` metric are included so that
    division-by-zero is avoided and recently-added items with no baseline are
    excluded from growth calculations.

    Args:
        session: An active async database session.
        days: Lookback window (currently unused -- growth is based on the
              stored ``_previous`` snapshot columns).

    Returns:
        A dict with two keys:

        * ``hf_models`` -- list of dicts sorted by ``growth_percent`` desc.
        * ``github_repos`` -- list of dicts sorted by ``growth_percent`` desc.

        Each item dict contains: ``id``, ``identifier``, ``metric_current``,
        ``metric_previous``, ``growth_percent``, ``growth_absolute``.
    """

    log.info("computing_growth_rates", days=days)

    # -- HuggingFace models --------------------------------------------------

    hf_growth = (
        (
            (HFModel.downloads - HFModel.downloads_previous)
            * 100.0
            / HFModel.downloads_previous
        )
    )

    hf_stmt = (
        select(
            HFModel.id,
            HFModel.model_id,
            HFModel.name,
            HFModel.downloads,
            HFModel.downloads_previous,
            (HFModel.downloads - HFModel.downloads_previous).label("growth_absolute"),
            hf_growth.label("growth_percent"),
        )
        .where(HFModel.downloads_previous > 0)
        .order_by(hf_growth.desc())
    )

    hf_result = await session.execute(hf_stmt)
    hf_rows = hf_result.all()

    hf_models: list[dict[str, Any]] = [
        {
            "id": row.id,
            "identifier": row.model_id,
            "name": row.name,
            "metric_current": row.downloads,
            "metric_previous": row.downloads_previous,
            "growth_percent": round(float(row.growth_percent), 2),
            "growth_absolute": int(row.growth_absolute),
        }
        for row in hf_rows
    ]

    # -- GitHub repos --------------------------------------------------------

    gh_growth = (
        (
            (GitHubRepo.stars - GitHubRepo.stars_previous)
            * 100.0
            / GitHubRepo.stars_previous
        )
    )

    gh_stmt = (
        select(
            GitHubRepo.id,
            GitHubRepo.full_name,
            GitHubRepo.name,
            GitHubRepo.stars,
            GitHubRepo.stars_previous,
            (GitHubRepo.stars - GitHubRepo.stars_previous).label("growth_absolute"),
            gh_growth.label("growth_percent"),
        )
        .where(GitHubRepo.stars_previous > 0)
        .order_by(gh_growth.desc())
    )

    gh_result = await session.execute(gh_stmt)
    gh_rows = gh_result.all()

    github_repos: list[dict[str, Any]] = [
        {
            "id": row.id,
            "identifier": row.full_name,
            "name": row.name,
            "metric_current": row.stars,
            "metric_previous": row.stars_previous,
            "growth_percent": round(float(row.growth_percent), 2),
            "growth_absolute": int(row.growth_absolute),
        }
        for row in gh_rows
    ]

    log.info(
        "growth_rates_computed",
        hf_count=len(hf_models),
        gh_count=len(github_repos),
    )

    return {"hf_models": hf_models, "github_repos": github_repos}


# ---------------------------------------------------------------------------
# Top trending
# ---------------------------------------------------------------------------


async def get_top_trending(
    session: AsyncSession,
    limit: int = 10,
    source: str = "all",
) -> list[dict[str, Any]]:
    """Return the top trending items across all sources, ranked by growth rate.

    Args:
        session: An active async database session.
        limit: Maximum number of items to return.
        source: ``"all"``, ``"hf"``, or ``"github"`` to filter by source type.

    Returns:
        A list of dicts, each with: ``source_type``, ``identifier``, ``name``,
        ``metric_value``, ``growth_percent``.
    """

    log.info("fetching_top_trending", limit=limit, source=source)

    combined: list[dict[str, Any]] = []

    if source in ("all", "hf"):
        hf_growth = case(
            (HFModel.downloads_previous > 0,
             (HFModel.downloads - HFModel.downloads_previous) * 100.0
             / HFModel.downloads_previous),
            else_=0.0,
        )

        hf_stmt = (
            select(
                HFModel.model_id,
                HFModel.name,
                HFModel.downloads,
                hf_growth.label("growth_percent"),
            )
            .where(HFModel.downloads_previous > 0)
            .order_by(hf_growth.desc())
            .limit(limit)
        )

        hf_result = await session.execute(hf_stmt)
        for row in hf_result.all():
            combined.append(
                {
                    "source_type": "hf_model",
                    "identifier": row.model_id,
                    "name": row.name,
                    "metric_value": row.downloads,
                    "growth_percent": round(float(row.growth_percent), 2),
                }
            )

    if source in ("all", "github"):
        gh_growth = case(
            (GitHubRepo.stars_previous > 0,
             (GitHubRepo.stars - GitHubRepo.stars_previous) * 100.0
             / GitHubRepo.stars_previous),
            else_=0.0,
        )

        gh_stmt = (
            select(
                GitHubRepo.full_name,
                GitHubRepo.name,
                GitHubRepo.stars,
                gh_growth.label("growth_percent"),
            )
            .where(GitHubRepo.stars_previous > 0)
            .order_by(gh_growth.desc())
            .limit(limit)
        )

        gh_result = await session.execute(gh_stmt)
        for row in gh_result.all():
            combined.append(
                {
                    "source_type": "github_repo",
                    "identifier": row.full_name,
                    "name": row.name,
                    "metric_value": row.stars,
                    "growth_percent": round(float(row.growth_percent), 2),
                }
            )

    # Sort the combined list by growth rate descending, then trim to limit.
    combined.sort(key=lambda d: d["growth_percent"], reverse=True)
    return combined[:limit]


# ---------------------------------------------------------------------------
# Download timeline (for area charts)
# ---------------------------------------------------------------------------


async def get_download_timeline(
    session: AsyncSession,
    pipeline_tag: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate download counts grouped by ``pipeline_tag``.

    This produces data suitable for an area / bar chart showing total
    downloads per pipeline category.

    Args:
        session: An active async database session.
        pipeline_tag: If supplied, limit results to this single tag.

    Returns:
        A list of dicts with ``pipeline_tag``, ``total_downloads``, and
        ``model_count``.
    """

    log.info("fetching_download_timeline", pipeline_tag=pipeline_tag)

    stmt = select(
        func.coalesce(HFModel.pipeline_tag, "unknown").label("pipeline_tag"),
        func.sum(HFModel.downloads).label("total_downloads"),
        func.count(HFModel.id).label("model_count"),
    ).group_by(
        func.coalesce(HFModel.pipeline_tag, "unknown"),
    )

    if pipeline_tag is not None:
        stmt = stmt.where(HFModel.pipeline_tag == pipeline_tag)

    stmt = stmt.order_by(func.sum(HFModel.downloads).desc())

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "pipeline_tag": row.pipeline_tag,
            "total_downloads": int(row.total_downloads or 0),
            "model_count": int(row.model_count),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Overview stats
# ---------------------------------------------------------------------------


async def get_overview_stats(session: AsyncSession) -> dict[str, Any]:
    """Compute dashboard overview metrics.

    Returns:
        A dict with: ``total_models``, ``total_repos``, ``total_papers``,
        ``total_niches``, ``active_signals``, ``total_downloads``.
    """

    log.info("computing_overview_stats")

    total_models = (await session.execute(select(func.count(HFModel.id)))).scalar_one()
    total_repos = (
        await session.execute(select(func.count(GitHubRepo.id)))
    ).scalar_one()
    total_papers = (
        await session.execute(select(func.count(ArxivPaper.id)))
    ).scalar_one()
    total_niches = (
        await session.execute(
            select(func.count(Niche.id)).where(Niche.is_active.is_(True))
        )
    ).scalar_one()
    active_signals = (
        await session.execute(
            select(func.count(TrendSignal.id)).where(
                TrendSignal.is_read.is_(False)
            )
        )
    ).scalar_one()
    total_downloads = (
        await session.execute(
            select(func.coalesce(func.sum(HFModel.downloads), 0))
        )
    ).scalar_one()

    stats: dict[str, Any] = {
        "total_models": total_models,
        "total_repos": total_repos,
        "total_papers": total_papers,
        "total_niches": total_niches,
        "active_signals": active_signals,
        "total_downloads": int(total_downloads),
    }

    log.info("overview_stats_computed", **stats)
    return stats
