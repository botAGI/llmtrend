"""HuggingFace model and GitHub repository API routes.

Provides paginated listing with filtering and sorting for HuggingFace models
and GitHub repositories, plus detail views for individual models.
"""

from __future__ import annotations

import math
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    GitHubRepoItem,
    GitHubRepoListResponse,
    HFModelDetailResponse,
    HFModelItem,
    HFModelListResponse,
    NicheBrief,
)
from app.dependencies import DBSession
from app.models.github_repo import GitHubRepo
from app.models.hf_model import HFModel

router = APIRouter(prefix="/api/models", tags=["models"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hf_growth_expr():
    """SQLAlchemy expression for HF model download growth percentage."""
    return case(
        (
            HFModel.downloads_previous > 0,
            (HFModel.downloads - HFModel.downloads_previous)
            * 100.0
            / HFModel.downloads_previous,
        ),
        else_=0.0,
    )


def _gh_growth_expr():
    """SQLAlchemy expression for GitHub repo star growth percentage."""
    return case(
        (
            GitHubRepo.stars_previous > 0,
            (GitHubRepo.stars - GitHubRepo.stars_previous)
            * 100.0
            / GitHubRepo.stars_previous,
        ),
        else_=0.0,
    )


# ---------------------------------------------------------------------------
# HuggingFace models
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=HFModelListResponse,
    summary="List HuggingFace models",
    description="Paginated listing of HuggingFace models with filtering, sorting, and search.",
)
async def list_models(
    db: DBSession,
    search: str | None = Query(default=None, description="Search model_id or name"),
    pipeline_tag: str | None = Query(default=None, description="Filter by pipeline tag"),
    author: str | None = Query(default=None, description="Filter by author"),
    sort_by: Literal["downloads", "likes", "trending_score", "growth"] = Query(
        default="downloads",
        description="Sort field",
    ),
    order: Literal["asc", "desc"] = Query(default="desc", description="Sort order"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> HFModelListResponse:
    """List HF models with filtering, sorting, pagination."""
    # -- Base count query and data query ------------------------------------
    count_stmt = select(func.count(HFModel.id))
    data_stmt = select(HFModel)

    # -- Apply filters ------------------------------------------------------
    if search:
        search_pattern = f"%{search}%"
        search_filter = HFModel.model_id.ilike(search_pattern) | HFModel.name.ilike(
            search_pattern
        )
        count_stmt = count_stmt.where(search_filter)
        data_stmt = data_stmt.where(search_filter)

    if pipeline_tag:
        count_stmt = count_stmt.where(HFModel.pipeline_tag == pipeline_tag)
        data_stmt = data_stmt.where(HFModel.pipeline_tag == pipeline_tag)

    if author:
        count_stmt = count_stmt.where(HFModel.author == author)
        data_stmt = data_stmt.where(HFModel.author == author)

    # -- Total count --------------------------------------------------------
    total: int = (await db.execute(count_stmt)).scalar_one()

    # -- Sorting ------------------------------------------------------------
    growth_expr = _hf_growth_expr()

    sort_column_map = {
        "downloads": HFModel.downloads,
        "likes": HFModel.likes,
        "trending_score": HFModel.trending_score,
        "growth": growth_expr,
    }
    sort_col = sort_column_map[sort_by]

    if order == "desc":
        data_stmt = data_stmt.order_by(sort_col.desc().nulls_last())
    else:
        data_stmt = data_stmt.order_by(sort_col.asc().nulls_last())

    # -- Pagination ---------------------------------------------------------
    offset = (page - 1) * per_page
    data_stmt = data_stmt.offset(offset).limit(per_page)

    result = await db.execute(data_stmt)
    models = result.scalars().all()

    pages = math.ceil(total / per_page) if total > 0 else 1

    items = [
        HFModelItem(
            id=m.id,
            model_id=m.model_id,
            name=m.name,
            author=m.author,
            pipeline_tag=m.pipeline_tag,
            library_name=m.library_name,
            tags=m.tags or [],
            downloads=m.downloads,
            downloads_previous=m.downloads_previous,
            downloads_growth_percent=m.downloads_growth_percent,
            likes=m.likes,
            likes_previous=m.likes_previous,
            likes_growth_percent=m.likes_growth_percent,
            trending_score=m.trending_score,
            last_modified=m.last_modified,
            first_seen_at=m.first_seen_at,
            last_seen_at=m.last_seen_at,
        )
        for m in models
    ]

    return HFModelListResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# GitHub repositories
# ---------------------------------------------------------------------------


@router.get(
    "/github",
    response_model=GitHubRepoListResponse,
    summary="List GitHub repositories",
    description="Paginated listing of GitHub repositories with filtering and sorting.",
)
async def list_github_repos(
    db: DBSession,
    search: str | None = Query(default=None, description="Search full_name or name"),
    language: str | None = Query(default=None, description="Filter by primary language"),
    sort_by: Literal["stars", "forks", "growth"] = Query(
        default="stars",
        description="Sort field",
    ),
    order: Literal["asc", "desc"] = Query(default="desc", description="Sort order"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> GitHubRepoListResponse:
    """List GitHub repos with filtering, sorting, pagination."""
    count_stmt = select(func.count(GitHubRepo.id))
    data_stmt = select(GitHubRepo)

    # -- Filters ------------------------------------------------------------
    if search:
        search_pattern = f"%{search}%"
        search_filter = GitHubRepo.full_name.ilike(
            search_pattern
        ) | GitHubRepo.name.ilike(search_pattern)
        count_stmt = count_stmt.where(search_filter)
        data_stmt = data_stmt.where(search_filter)

    if language:
        count_stmt = count_stmt.where(GitHubRepo.language == language)
        data_stmt = data_stmt.where(GitHubRepo.language == language)

    # -- Total count --------------------------------------------------------
    total: int = (await db.execute(count_stmt)).scalar_one()

    # -- Sorting ------------------------------------------------------------
    growth_expr = _gh_growth_expr()

    sort_column_map = {
        "stars": GitHubRepo.stars,
        "forks": GitHubRepo.forks,
        "growth": growth_expr,
    }
    sort_col = sort_column_map[sort_by]

    if order == "desc":
        data_stmt = data_stmt.order_by(sort_col.desc().nulls_last())
    else:
        data_stmt = data_stmt.order_by(sort_col.asc().nulls_last())

    # -- Pagination ---------------------------------------------------------
    offset = (page - 1) * per_page
    data_stmt = data_stmt.offset(offset).limit(per_page)

    result = await db.execute(data_stmt)
    repos = result.scalars().all()

    pages = math.ceil(total / per_page) if total > 0 else 1

    items = [
        GitHubRepoItem(
            id=r.id,
            full_name=r.full_name,
            name=r.name,
            owner_login=r.owner_login,
            description=r.description,
            html_url=r.html_url,
            language=r.language,
            topics=r.topics or [],
            stars=r.stars,
            stars_previous=r.stars_previous,
            stars_growth_percent=r.stars_growth_percent,
            forks=r.forks,
            open_issues=r.open_issues,
            license_spdx=r.license_spdx,
            repo_created_at=r.repo_created_at,
            repo_pushed_at=r.repo_pushed_at,
            first_seen_at=r.first_seen_at,
            last_seen_at=r.last_seen_at,
        )
        for r in repos
    ]

    return GitHubRepoListResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Model detail (supports slashes in model_id via path param)
# ---------------------------------------------------------------------------


@router.get(
    "/{model_id:path}",
    response_model=HFModelDetailResponse,
    summary="Get model detail",
    description=(
        "Get detailed information about a HuggingFace model by its model_id. "
        "Supports slash-containing identifiers like 'meta-llama/Llama-3.1-8B'."
    ),
)
async def get_model(model_id: str, db: DBSession) -> HFModelDetailResponse:
    """Get HF model detail by model_id (path param to support slashes)."""
    # Avoid collision with the /github sub-route
    if model_id == "github":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found. Did you mean /api/models/github?",
        )

    stmt = select(HFModel).where(HFModel.model_id == model_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()

    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    niche_briefs = [
        NicheBrief(id=n.id, name=n.name, slug=n.slug) for n in (model.niches or [])
    ]

    return HFModelDetailResponse(
        id=model.id,
        model_id=model.model_id,
        name=model.name,
        author=model.author,
        pipeline_tag=model.pipeline_tag,
        library_name=model.library_name,
        tags=model.tags or [],
        downloads=model.downloads,
        downloads_previous=model.downloads_previous,
        downloads_growth_percent=model.downloads_growth_percent,
        likes=model.likes,
        likes_previous=model.likes_previous,
        likes_growth_percent=model.likes_growth_percent,
        trending_score=model.trending_score,
        is_private=model.is_private,
        last_modified=model.last_modified,
        first_seen_at=model.first_seen_at,
        last_seen_at=model.last_seen_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        niches=niche_briefs,
    )
