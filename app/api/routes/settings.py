"""System settings and administration API routes.

Provides system health checks, data collection triggers, and analytics
pipeline execution endpoints.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.llm_analyzer import LLMAnalyzer
from app.api.schemas import (
    CollectionRunInfo,
    DatabaseCounts,
    OllamaStatus,
    SystemStatusResponse,
    TaskQueuedResponse,
)
from app.dependencies import DBSession, SettingsDep
from app.models.arxiv_paper import ArxivPaper
from app.models.collection_run import CollectionRun
from app.models.github_repo import GitHubRepo
from app.models.hf_model import HFModel
from app.models.niche import Niche
from app.models.report import Report
from app.models.trend_signal import TrendSignal
from app.tasks.analytics_tasks import (
    generate_daily_report_task,
    generate_weekly_report_task,
    run_analytics_task,
)
from app.tasks.collection_tasks import collect_all_task, collect_source_task

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Source types we track collection runs for
# ---------------------------------------------------------------------------

_SOURCE_TYPES: list[str] = ["huggingface", "github", "arxiv"]


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="System status",
    description=(
        "System health check returning the latest collection runs per source, "
        "database record counts, and Ollama LLM service status."
    ),
)
async def system_status(
    db: DBSession,
    settings: SettingsDep,
) -> SystemStatusResponse:
    """System health: last collection runs, DB stats, Ollama status."""
    # -- Latest collection run per source -----------------------------------
    latest_runs: list[CollectionRunInfo] = []

    for source in _SOURCE_TYPES:
        stmt = (
            select(CollectionRun)
            .where(CollectionRun.source_type == source)
            .order_by(CollectionRun.started_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if run is not None:
            latest_runs.append(
                CollectionRunInfo(
                    id=run.id,
                    source_type=run.source_type,
                    status=run.status,
                    items_fetched=run.items_fetched,
                    items_created=run.items_created,
                    items_updated=run.items_updated,
                    error_message=run.error_message,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    duration_seconds=run.duration_seconds,
                )
            )

    # -- Database record counts ---------------------------------------------
    hf_count: int = (await db.execute(select(func.count(HFModel.id)))).scalar_one()
    gh_count: int = (await db.execute(select(func.count(GitHubRepo.id)))).scalar_one()
    arxiv_count: int = (await db.execute(select(func.count(ArxivPaper.id)))).scalar_one()
    niche_count: int = (await db.execute(select(func.count(Niche.id)))).scalar_one()
    signal_count: int = (await db.execute(select(func.count(TrendSignal.id)))).scalar_one()
    report_count: int = (await db.execute(select(func.count(Report.id)))).scalar_one()
    run_count: int = (await db.execute(select(func.count(CollectionRun.id)))).scalar_one()

    db_counts = DatabaseCounts(
        hf_models=hf_count,
        github_repos=gh_count,
        arxiv_papers=arxiv_count,
        niches=niche_count,
        signals=signal_count,
        reports=report_count,
        collection_runs=run_count,
    )

    # -- Ollama status ------------------------------------------------------
    analyzer = LLMAnalyzer()
    ollama_info = await analyzer.get_status()

    ollama = OllamaStatus(
        available=ollama_info.get("available", False),
        enabled=ollama_info.get("enabled", False),
        model=ollama_info.get("model", ""),
        models_available=ollama_info.get("models_available", []),
        models_running=ollama_info.get("models_running", []),
    )

    return SystemStatusResponse(
        environment=settings.APP_ENV,
        database=db_counts,
        ollama=ollama,
        latest_collection_runs=latest_runs,
    )


@router.post(
    "/collect",
    response_model=TaskQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger data collection",
    description=(
        "Queue a data collection task. Specify 'all' to collect from every source, "
        "or a specific source name (huggingface, github, arxiv)."
    ),
)
async def trigger_collection(
    source: str = Query(
        default="all",
        description="Source to collect: all, huggingface, github, arxiv",
    ),
) -> TaskQueuedResponse:
    """Trigger data collection. Queues a Celery task."""
    source_lower = source.lower().strip()

    valid_sources = {"all", "huggingface", "github", "arxiv"}
    if source_lower not in valid_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid source '{source}'. "
                f"Valid options: {', '.join(sorted(valid_sources))}"
            ),
        )

    if source_lower == "all":
        task = collect_all_task.delay()
    else:
        task = collect_source_task.delay(source_lower)

    return TaskQueuedResponse(task_id=task.id, status="queued")


@router.post(
    "/analyze",
    response_model=TaskQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger analytics pipeline",
    description=(
        "Queue the full analytics pipeline: growth rate computation, signal "
        "detection, and niche assignment."
    ),
)
async def trigger_analytics() -> TaskQueuedResponse:
    """Trigger analytics pipeline. Queues a Celery task."""
    task = run_analytics_task.delay()
    return TaskQueuedResponse(task_id=task.id, status="queued")
