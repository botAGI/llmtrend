"""Niche aggregation and classification for the AI Trend Monitor.

Manages default niche definitions, assigns tracked models and repositories to
niches based on keyword matching, and provides summary and detail views.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arxiv_paper import ArxivPaper
from app.models.github_repo import GitHubRepo
from app.models.hf_model import HFModel
from app.models.niche import Niche, niche_arxiv_papers, niche_github_repos, niche_hf_models
from app.models.trend_signal import TrendSignal
from app.utils.helpers import slugify, utc_now

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Default niche definitions
# ---------------------------------------------------------------------------

DEFAULT_NICHES: dict[str, list[str]] = {
    "Text Generation / LLMs": [
        "text-generation", "llm", "language-model", "chat", "instruction",
    ],
    "Code Generation": [
        "code", "coding", "copilot", "code-generation", "programming",
    ],
    "Image Generation": [
        "text-to-image", "image-generation", "diffusion", "stable-diffusion", "dalle",
    ],
    "Computer Vision": [
        "computer-vision", "image-classification", "object-detection", "segmentation",
    ],
    "Speech & Audio": [
        "speech", "audio", "text-to-speech", "speech-recognition", "whisper", "tts",
    ],
    "Video Generation": [
        "text-to-video", "video-generation", "video",
    ],
    "NLP / Text Analysis": [
        "text-classification", "sentiment", "ner", "token-classification", "summarization",
    ],
    "Translation": [
        "translation", "machine-translation", "nllb",
    ],
    "RAG & Search": [
        "rag", "retrieval", "embedding", "vector", "search",
    ],
    "AI Agents": [
        "agent", "ai-agent", "autonomous", "tool-use",
    ],
    "Multimodal": [
        "multimodal", "vision-language", "vlm", "visual-question-answering",
    ],
    "Robotics": [
        "robotics", "robot", "manipulation", "control",
    ],
    "Healthcare AI": [
        "medical", "healthcare", "clinical", "biomedical", "drug",
    ],
    "Finance AI": [
        "finance", "trading", "financial", "stock",
    ],
    "Scientific Research": [
        "science", "scientific", "chemistry", "physics", "biology", "protein",
    ],
}


# ---------------------------------------------------------------------------
# Niche seeding
# ---------------------------------------------------------------------------


async def ensure_default_niches(session: AsyncSession) -> None:
    """Create default niches if they do not already exist.

    Existing niches (matched by slug) are left unchanged.
    """

    log.info("ensuring_default_niches")

    existing_stmt = select(Niche.slug)
    existing_result = await session.execute(existing_stmt)
    existing_slugs: set[str] = {row[0] for row in existing_result.all()}

    created = 0
    for name, keywords in DEFAULT_NICHES.items():
        slug = slugify(name)
        if slug in existing_slugs:
            continue

        niche = Niche(
            name=name,
            slug=slug,
            keywords=keywords,
            is_active=True,
        )
        session.add(niche)
        created += 1

    if created > 0:
        await session.flush()

    log.info("default_niches_ensured", created=created, existing=len(existing_slugs))


# ---------------------------------------------------------------------------
# Assignment engine
# ---------------------------------------------------------------------------


def _matches_keywords(
    keywords: list[str],
    *,
    tags: list[str] | None = None,
    pipeline_tag: str | None = None,
    name: str | None = None,
    topics: list[str] | None = None,
    description: str | None = None,
) -> bool:
    """Return ``True`` if any keyword appears in the provided fields."""

    searchable_parts: list[str] = []

    if tags:
        searchable_parts.extend(t.lower() for t in tags)
    if pipeline_tag:
        searchable_parts.append(pipeline_tag.lower())
    if name:
        searchable_parts.append(name.lower())
    if topics:
        searchable_parts.extend(t.lower() for t in topics)
    if description:
        searchable_parts.append(description.lower())

    # Build a single haystack for substring matching against keywords
    haystack = " ".join(searchable_parts)

    for kw in keywords:
        kw_lower = kw.lower()
        # Exact token match in list-based fields
        if tags and kw_lower in [t.lower() for t in tags]:
            return True
        if topics and kw_lower in [t.lower() for t in topics]:
            return True
        if pipeline_tag and kw_lower == pipeline_tag.lower():
            return True
        # Substring match in name / description
        if kw_lower in haystack:
            return True

    return False


async def assign_models_to_niches(session: AsyncSession) -> int:
    """Assign HuggingFace models and GitHub repos to niches via keyword matching.

    For each active niche, models are matched against the niche's keyword list
    using their ``tags``, ``pipeline_tag``, and ``name``.  Repos are matched
    against ``topics``, ``description``, and ``name``.

    Existing assignments are preserved; only new associations are created.

    Returns:
        The number of new assignments created.
    """

    log.info("assigning_models_to_niches")

    # Load all active niches
    niche_stmt = select(Niche).where(Niche.is_active.is_(True))
    niche_result = await session.execute(niche_stmt)
    niches: list[Niche] = list(niche_result.scalars().all())

    if not niches:
        log.warning("no_active_niches_found")
        return 0

    # Load existing HF model assignments
    existing_hf_stmt = select(
        niche_hf_models.c.niche_id, niche_hf_models.c.hf_model_id
    )
    existing_hf_result = await session.execute(existing_hf_stmt)
    existing_hf_pairs: set[tuple[int, int]] = {
        (row[0], row[1]) for row in existing_hf_result.all()
    }

    # Load existing GitHub repo assignments
    existing_gh_stmt = select(
        niche_github_repos.c.niche_id, niche_github_repos.c.github_repo_id
    )
    existing_gh_result = await session.execute(existing_gh_stmt)
    existing_gh_pairs: set[tuple[int, int]] = {
        (row[0], row[1]) for row in existing_gh_result.all()
    }

    # Load all HF models
    hf_result = await session.execute(select(HFModel))
    all_hf_models: list[HFModel] = list(hf_result.scalars().all())

    # Load all GitHub repos
    gh_result = await session.execute(select(GitHubRepo))
    all_gh_repos: list[GitHubRepo] = list(gh_result.scalars().all())

    new_assignments = 0

    for niche in niches:
        keywords: list[str] = niche.keywords or []
        if not keywords:
            continue

        # -- HF models -------------------------------------------------------
        for model in all_hf_models:
            if (niche.id, model.id) in existing_hf_pairs:
                continue

            if _matches_keywords(
                keywords,
                tags=model.tags,
                pipeline_tag=model.pipeline_tag,
                name=model.name,
            ):
                stmt = niche_hf_models.insert().values(
                    niche_id=niche.id,
                    hf_model_id=model.id,
                    confidence=1.0,
                )
                await session.execute(stmt)
                existing_hf_pairs.add((niche.id, model.id))
                new_assignments += 1

        # -- GitHub repos ----------------------------------------------------
        for repo in all_gh_repos:
            if (niche.id, repo.id) in existing_gh_pairs:
                continue

            if _matches_keywords(
                keywords,
                topics=repo.topics,
                description=repo.description,
                name=repo.name,
            ):
                stmt = niche_github_repos.insert().values(
                    niche_id=niche.id,
                    github_repo_id=repo.id,
                    confidence=1.0,
                )
                await session.execute(stmt)
                existing_gh_pairs.add((niche.id, repo.id))
                new_assignments += 1

    await session.flush()

    log.info("niche_assignment_complete", new_assignments=new_assignments)
    return new_assignments


# ---------------------------------------------------------------------------
# Niche summaries
# ---------------------------------------------------------------------------


async def get_niche_summary(
    session: AsyncSession,
    niche_id: int | None = None,
) -> list[dict[str, Any]]:
    """Get summary statistics for all niches or a specific one.

    Args:
        session: An active async database session.
        niche_id: If provided, return summary for this niche only.

    Returns:
        A list of dicts, each containing: ``niche_id``, ``name``, ``slug``,
        ``model_count``, ``repo_count``, ``paper_count``, ``total_downloads``,
        ``avg_growth_percent``, ``top_model``.
    """

    log.info("fetching_niche_summary", niche_id=niche_id)

    niche_stmt = select(Niche).where(Niche.is_active.is_(True))
    if niche_id is not None:
        niche_stmt = niche_stmt.where(Niche.id == niche_id)
    niche_stmt = niche_stmt.order_by(Niche.name)

    niche_result = await session.execute(niche_stmt)
    niches: list[Niche] = list(niche_result.scalars().all())

    summaries: list[dict[str, Any]] = []

    for niche in niches:
        # Model count
        model_count_result = await session.execute(
            select(func.count(niche_hf_models.c.hf_model_id)).where(
                niche_hf_models.c.niche_id == niche.id
            )
        )
        model_count: int = model_count_result.scalar_one()

        # Repo count
        repo_count_result = await session.execute(
            select(func.count(niche_github_repos.c.github_repo_id)).where(
                niche_github_repos.c.niche_id == niche.id
            )
        )
        repo_count: int = repo_count_result.scalar_one()

        # Paper count
        paper_count_result = await session.execute(
            select(func.count(niche_arxiv_papers.c.arxiv_paper_id)).where(
                niche_arxiv_papers.c.niche_id == niche.id
            )
        )
        paper_count: int = paper_count_result.scalar_one()

        # Total downloads and avg growth for niche models
        dl_stmt = (
            select(
                func.coalesce(func.sum(HFModel.downloads), 0).label("total_dl"),
                func.avg(
                    func.nullif(
                        (HFModel.downloads - HFModel.downloads_previous)
                        * 100.0
                        / func.nullif(HFModel.downloads_previous, 0),
                        None,
                    )
                ).label("avg_growth"),
            )
            .select_from(HFModel)
            .join(
                niche_hf_models,
                and_(
                    niche_hf_models.c.hf_model_id == HFModel.id,
                    niche_hf_models.c.niche_id == niche.id,
                ),
            )
        )
        dl_result = await session.execute(dl_stmt)
        dl_row = dl_result.one()
        total_downloads = int(dl_row.total_dl or 0)
        avg_growth = round(float(dl_row.avg_growth or 0.0), 2)

        # Top model by downloads
        top_model_stmt = (
            select(HFModel.model_id, HFModel.downloads)
            .join(
                niche_hf_models,
                and_(
                    niche_hf_models.c.hf_model_id == HFModel.id,
                    niche_hf_models.c.niche_id == niche.id,
                ),
            )
            .order_by(HFModel.downloads.desc())
            .limit(1)
        )
        top_model_result = await session.execute(top_model_stmt)
        top_model_row = top_model_result.first()
        top_model: str | None = top_model_row.model_id if top_model_row else None

        summaries.append(
            {
                "niche_id": niche.id,
                "name": niche.name,
                "slug": niche.slug,
                "model_count": model_count,
                "repo_count": repo_count,
                "paper_count": paper_count,
                "total_downloads": total_downloads,
                "avg_growth_percent": avg_growth,
                "top_model": top_model,
            }
        )

    return summaries


# ---------------------------------------------------------------------------
# Niche detail
# ---------------------------------------------------------------------------


async def get_niche_detail(
    session: AsyncSession,
    niche_id: int,
) -> dict[str, Any]:
    """Get a detailed view of a single niche.

    Args:
        session: An active async database session.
        niche_id: The primary key of the niche.

    Returns:
        A dict with: ``niche`` (basic info), ``top_models``, ``top_repos``,
        ``recent_papers``, ``recent_signals``.

    Raises:
        ValueError: If no niche with the given ID exists.
    """

    log.info("fetching_niche_detail", niche_id=niche_id)

    niche_result = await session.execute(
        select(Niche).where(Niche.id == niche_id)
    )
    niche: Niche | None = niche_result.scalar_one_or_none()
    if niche is None:
        raise ValueError(f"Niche with id={niche_id} not found")

    # Top models by downloads
    top_models_stmt = (
        select(HFModel)
        .join(
            niche_hf_models,
            and_(
                niche_hf_models.c.hf_model_id == HFModel.id,
                niche_hf_models.c.niche_id == niche_id,
            ),
        )
        .order_by(HFModel.downloads.desc())
        .limit(10)
    )
    top_models_result = await session.execute(top_models_stmt)
    top_models: list[dict[str, Any]] = [
        {
            "id": m.id,
            "model_id": m.model_id,
            "name": m.name,
            "author": m.author,
            "pipeline_tag": m.pipeline_tag,
            "downloads": m.downloads,
            "growth_percent": m.downloads_growth_percent,
        }
        for m in top_models_result.scalars().all()
    ]

    # Top repos by stars
    top_repos_stmt = (
        select(GitHubRepo)
        .join(
            niche_github_repos,
            and_(
                niche_github_repos.c.github_repo_id == GitHubRepo.id,
                niche_github_repos.c.niche_id == niche_id,
            ),
        )
        .order_by(GitHubRepo.stars.desc())
        .limit(10)
    )
    top_repos_result = await session.execute(top_repos_stmt)
    top_repos: list[dict[str, Any]] = [
        {
            "id": r.id,
            "full_name": r.full_name,
            "name": r.name,
            "stars": r.stars,
            "language": r.language,
            "growth_percent": r.stars_growth_percent,
        }
        for r in top_repos_result.scalars().all()
    ]

    # Recent papers
    recent_papers_stmt = (
        select(ArxivPaper)
        .join(
            niche_arxiv_papers,
            and_(
                niche_arxiv_papers.c.arxiv_paper_id == ArxivPaper.id,
                niche_arxiv_papers.c.niche_id == niche_id,
            ),
        )
        .order_by(ArxivPaper.published_at.desc())
        .limit(10)
    )
    recent_papers_result = await session.execute(recent_papers_stmt)
    recent_papers: list[dict[str, Any]] = [
        {
            "id": p.id,
            "arxiv_id": p.arxiv_id,
            "title": p.title,
            "primary_category": p.primary_category,
            "published_at": p.published_at.isoformat(),
        }
        for p in recent_papers_result.scalars().all()
    ]

    # Recent signals for this niche
    recent_signals_stmt = (
        select(TrendSignal)
        .where(TrendSignal.niche_id == niche_id)
        .order_by(TrendSignal.detected_at.desc())
        .limit(10)
    )
    recent_signals_result = await session.execute(recent_signals_stmt)
    recent_signals: list[dict[str, Any]] = [
        {
            "id": s.id,
            "signal_type": s.signal_type,
            "severity": s.severity,
            "source_identifier": s.source_identifier,
            "description": s.description,
            "detected_at": s.detected_at.isoformat(),
        }
        for s in recent_signals_result.scalars().all()
    ]

    return {
        "niche": {
            "id": niche.id,
            "name": niche.name,
            "slug": niche.slug,
            "keywords": niche.keywords,
            "is_active": niche.is_active,
        },
        "top_models": top_models,
        "top_repos": top_repos,
        "recent_papers": recent_papers,
        "recent_signals": recent_signals,
    }
