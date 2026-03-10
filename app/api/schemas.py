"""Pydantic response models for the AI Trend Monitor API.

All response schemas are defined here to provide consistent, typed API
responses with automatic OpenAPI documentation generation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared / generic
# ---------------------------------------------------------------------------


class PaginationMeta(BaseModel):
    """Pagination metadata included in paginated list responses."""

    total: int = Field(description="Total number of items matching the query")
    page: int = Field(description="Current page number (1-indexed)")
    per_page: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")


class MessageResponse(BaseModel):
    """Simple message response for actions that return status text."""

    message: str


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class OverviewStats(BaseModel):
    """Aggregate counts for the dashboard overview."""

    total_models: int = 0
    total_repos: int = 0
    total_papers: int = 0
    total_niches: int = 0
    active_signals: int = 0
    total_downloads: int = 0


class TrendingItem(BaseModel):
    """A single trending entity across any source type."""

    source_type: str
    identifier: str
    name: str
    metric_value: int
    growth_percent: float


class RecentSignalItem(BaseModel):
    """Compact representation of a recent signal for the overview."""

    id: int
    signal_type: str
    severity: str
    source_type: str
    source_identifier: str
    description: str | None = None
    detected_at: datetime


class OverviewResponse(BaseModel):
    """Full dashboard overview payload."""

    stats: OverviewStats
    trending: list[TrendingItem]
    recent_signals: list[RecentSignalItem]


class TimelineDataPoint(BaseModel):
    """A single data point in the download timeline."""

    pipeline_tag: str
    total_downloads: int
    model_count: int


class TimelineResponse(BaseModel):
    """Download timeline response."""

    timeline: list[TimelineDataPoint]


# ---------------------------------------------------------------------------
# HuggingFace models
# ---------------------------------------------------------------------------


class HFModelItem(BaseModel):
    """Serialized HuggingFace model for list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    model_id: str
    name: str
    author: str | None = None
    pipeline_tag: str | None = None
    library_name: str | None = None
    tags: list[Any] = Field(default_factory=list)
    downloads: int = 0
    downloads_previous: int = 0
    downloads_growth_percent: float | None = None
    likes: int = 0
    likes_previous: int = 0
    likes_growth_percent: float | None = None
    trending_score: float | None = None
    last_modified: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime


class HFModelListResponse(BaseModel):
    """Paginated list of HuggingFace models."""

    items: list[HFModelItem]
    total: int
    page: int
    pages: int


class HFModelDetailResponse(BaseModel):
    """Detailed view of a single HuggingFace model."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    model_id: str
    name: str
    author: str | None = None
    pipeline_tag: str | None = None
    library_name: str | None = None
    tags: list[Any] = Field(default_factory=list)
    downloads: int = 0
    downloads_previous: int = 0
    downloads_growth_percent: float | None = None
    likes: int = 0
    likes_previous: int = 0
    likes_growth_percent: float | None = None
    trending_score: float | None = None
    is_private: bool = False
    last_modified: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    niches: list[NicheBrief] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GitHub repos
# ---------------------------------------------------------------------------


class GitHubRepoItem(BaseModel):
    """Serialized GitHub repository for list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    name: str
    owner_login: str
    description: str | None = None
    html_url: str
    language: str | None = None
    topics: list[Any] = Field(default_factory=list)
    stars: int = 0
    stars_previous: int = 0
    stars_growth_percent: float | None = None
    forks: int = 0
    open_issues: int = 0
    license_spdx: str | None = None
    repo_created_at: datetime | None = None
    repo_pushed_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime


class GitHubRepoListResponse(BaseModel):
    """Paginated list of GitHub repositories."""

    items: list[GitHubRepoItem]
    total: int
    page: int
    pages: int


# ---------------------------------------------------------------------------
# Niches
# ---------------------------------------------------------------------------


class NicheBrief(BaseModel):
    """Minimal niche reference used in nested responses."""

    id: int
    name: str
    slug: str


class NicheSummaryItem(BaseModel):
    """Summary stats for a single niche."""

    niche_id: int
    name: str
    slug: str
    model_count: int = 0
    repo_count: int = 0
    paper_count: int = 0
    total_downloads: int = 0
    avg_growth_percent: float = 0.0
    top_model: str | None = None


class NicheListResponse(BaseModel):
    """List of niche summaries."""

    niches: list[NicheSummaryItem]
    total: int


class NicheModelItem(BaseModel):
    """Model brief within a niche detail."""

    id: int
    model_id: str
    name: str
    author: str | None = None
    pipeline_tag: str | None = None
    downloads: int = 0
    growth_percent: float | None = None


class NicheRepoItem(BaseModel):
    """Repo brief within a niche detail."""

    id: int
    full_name: str
    name: str
    stars: int = 0
    language: str | None = None
    growth_percent: float | None = None


class NichePaperItem(BaseModel):
    """Paper brief within a niche detail."""

    id: int
    arxiv_id: str
    title: str
    primary_category: str
    published_at: str


class NicheSignalItem(BaseModel):
    """Signal brief within a niche detail."""

    id: int
    signal_type: str
    severity: str
    source_identifier: str
    description: str | None = None
    detected_at: str


class NicheInfo(BaseModel):
    """Core niche metadata."""

    id: int
    name: str
    slug: str
    keywords: list[str] = Field(default_factory=list)
    is_active: bool = True


class NicheDetailResponse(BaseModel):
    """Detailed view of a single niche."""

    niche: NicheInfo
    top_models: list[NicheModelItem]
    top_repos: list[NicheRepoItem]
    recent_papers: list[NichePaperItem]
    recent_signals: list[NicheSignalItem]


class NicheAnalysisResponse(BaseModel):
    """Response from AI niche analysis."""

    niche_id: int
    niche_name: str
    analysis: str
    llm_available: bool


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


class SignalItem(BaseModel):
    """Serialized trend signal."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source_id: int
    source_identifier: str
    signal_type: str
    severity: str
    value: float
    delta: float | None = None
    delta_percent: float | None = None
    description: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    niche_id: int | None = None
    detected_at: datetime
    is_read: bool = False
    created_at: datetime


class SignalListResponse(BaseModel):
    """Paginated / offset-based list of signals."""

    items: list[SignalItem]
    total: int
    limit: int
    offset: int


class SignalStatsResponse(BaseModel):
    """Signal counts grouped by time period and type."""

    today: int = 0
    this_week: int = 0
    this_month: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)


class SignalReadResponse(BaseModel):
    """Confirmation that a signal was marked as read."""

    id: int
    is_read: bool


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class ReportItem(BaseModel):
    """Serialized report for list responses (no full content)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    report_type: str
    niche_id: int | None = None
    signals_count: int = 0
    period_start: datetime | None = None
    period_end: datetime | None = None
    generated_at: datetime
    generation_time_seconds: float | None = None
    llm_model_used: str | None = None
    file_path: str | None = None
    created_at: datetime


class ReportListResponse(BaseModel):
    """List of reports."""

    items: list[ReportItem]
    total: int


class ReportDetailResponse(BaseModel):
    """Full report including markdown content."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    report_type: str
    content_markdown: str
    content_html: str | None = None
    niche_id: int | None = None
    signals_count: int = 0
    period_start: datetime | None = None
    period_end: datetime | None = None
    generated_at: datetime
    generation_time_seconds: float | None = None
    llm_model_used: str | None = None
    file_path: str | None = None
    created_at: datetime


class ReportGenerateRequest(BaseModel):
    """Request body for report generation."""

    report_type: str = Field(description="One of: daily, weekly, niche")
    niche_id: int | None = Field(
        default=None,
        description="Required when report_type is 'niche'",
    )


class ReportGenerateResponse(BaseModel):
    """Response after generating a report."""

    id: int
    title: str
    report_type: str
    generated_at: datetime
    generation_time_seconds: float | None = None
    file_path: str | None = None


# ---------------------------------------------------------------------------
# Settings / system
# ---------------------------------------------------------------------------


class CollectionRunInfo(BaseModel):
    """Summary of the latest collection run for a source."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    status: str
    items_fetched: int = 0
    items_created: int = 0
    items_updated: int = 0
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None


class OllamaStatus(BaseModel):
    """Ollama service health information."""

    available: bool = False
    enabled: bool = False
    model: str = ""
    models_available: list[str] = Field(default_factory=list)
    models_running: list[str] = Field(default_factory=list)


class DatabaseCounts(BaseModel):
    """Record counts per table."""

    hf_models: int = 0
    github_repos: int = 0
    arxiv_papers: int = 0
    niches: int = 0
    signals: int = 0
    reports: int = 0
    collection_runs: int = 0


class SystemStatusResponse(BaseModel):
    """Full system health check response."""

    environment: str
    database: DatabaseCounts
    ollama: OllamaStatus
    latest_collection_runs: list[CollectionRunInfo]


class TaskQueuedResponse(BaseModel):
    """Response after queuing a Celery task."""

    task_id: str
    status: str = "queued"


# ---------------------------------------------------------------------------
# Forward reference resolution
# ---------------------------------------------------------------------------

# HFModelDetailResponse references NicheBrief which is defined above,
# so we rebuild the model to resolve forward refs.
HFModelDetailResponse.model_rebuild()
