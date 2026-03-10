"""Niche management API routes.

Provides listing, detail views, and AI-powered analysis for topic niches
that group related AI models, repositories, and papers.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status

from app.analytics.llm_analyzer import LLMAnalyzer
from app.analytics.niches import get_niche_detail, get_niche_summary
from app.api.schemas import (
    NicheAnalysisResponse,
    NicheDetailResponse,
    NicheInfo,
    NicheListResponse,
    NicheModelItem,
    NichePaperItem,
    NicheRepoItem,
    NicheSignalItem,
    NicheSummaryItem,
)
from app.dependencies import DBSession

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/niches", tags=["niches"])


@router.get(
    "/",
    response_model=NicheListResponse,
    summary="List niches",
    description="List all active niches with summary statistics.",
)
async def list_niches(db: DBSession) -> NicheListResponse:
    """List all niches with summary stats."""
    summaries = await get_niche_summary(db)

    items = [NicheSummaryItem(**s) for s in summaries]

    return NicheListResponse(niches=items, total=len(items))


@router.get(
    "/{niche_id}",
    response_model=NicheDetailResponse,
    summary="Get niche detail",
    description="Detailed view of a niche including its associated models, repos, papers, and signals.",
)
async def get_niche(niche_id: int, db: DBSession) -> NicheDetailResponse:
    """Get niche detail with associated models, repos, papers, signals."""
    try:
        detail = await get_niche_detail(db, niche_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Niche with id={niche_id} not found",
        )

    return NicheDetailResponse(
        niche=NicheInfo(**detail["niche"]),
        top_models=[NicheModelItem(**m) for m in detail["top_models"]],
        top_repos=[NicheRepoItem(**r) for r in detail["top_repos"]],
        recent_papers=[NichePaperItem(**p) for p in detail["recent_papers"]],
        recent_signals=[NicheSignalItem(**s) for s in detail["recent_signals"]],
    )


@router.post(
    "/{niche_id}/analyze",
    response_model=NicheAnalysisResponse,
    summary="Analyze niche with AI",
    description="Generate an AI-powered analysis summary for a specific niche using Ollama.",
)
async def analyze_niche(niche_id: int, db: DBSession) -> NicheAnalysisResponse:
    """Generate AI analysis for a niche using Ollama."""
    # Fetch niche detail to get context data
    try:
        detail = await get_niche_detail(db, niche_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Niche with id={niche_id} not found",
        )

    niche_info = detail["niche"]
    analyzer = LLMAnalyzer()
    llm_available = await analyzer.is_available()

    # Build context string from niche data for the LLM
    context_parts: list[str] = [
        f"Niche: {niche_info['name']}",
        f"Keywords: {', '.join(niche_info.get('keywords', []))}",
        "",
    ]

    top_models = detail.get("top_models", [])
    if top_models:
        context_parts.append("Top Models:")
        for m in top_models[:5]:
            growth_str = f"{m['growth_percent']:+.1f}%" if m.get("growth_percent") is not None else "N/A"
            context_parts.append(
                f"  - {m['model_id']}: {m['downloads']:,} downloads, growth: {growth_str}"
            )
        context_parts.append("")

    top_repos = detail.get("top_repos", [])
    if top_repos:
        context_parts.append("Top Repositories:")
        for r in top_repos[:5]:
            growth_str = f"{r['growth_percent']:+.1f}%" if r.get("growth_percent") is not None else "N/A"
            context_parts.append(
                f"  - {r['full_name']}: {r['stars']:,} stars, growth: {growth_str}"
            )
        context_parts.append("")

    recent_papers = detail.get("recent_papers", [])
    if recent_papers:
        context_parts.append(f"Recent Papers ({len(recent_papers)}):")
        for p in recent_papers[:5]:
            context_parts.append(f"  - {p['title']} ({p['arxiv_id']})")
        context_parts.append("")

    recent_signals = detail.get("recent_signals", [])
    if recent_signals:
        context_parts.append(f"Recent Signals ({len(recent_signals)}):")
        for s in recent_signals[:5]:
            context_parts.append(
                f"  - [{s['severity']}] {s['signal_type']}: {s['description']}"
            )

    context = "\n".join(context_parts)

    analysis = await analyzer.answer_question(
        question=(
            f"Provide a comprehensive analysis of the '{niche_info['name']}' niche. "
            "Cover current state, key trends, notable developments, and short-term outlook. "
            "Be specific and reference the data provided."
        ),
        context=context,
    )

    return NicheAnalysisResponse(
        niche_id=niche_id,
        niche_name=niche_info["name"],
        analysis=analysis,
        llm_available=llm_available,
    )
