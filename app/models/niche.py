"""ORM model for niches (topic clusters) and association tables for the AI Trend Monitor."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.hf_model import HFModel
    from app.models.github_repo import GitHubRepo
    from app.models.arxiv_paper import ArxivPaper
    from app.models.trend_signal import TrendSignal
    from app.models.report import Report

# ---------------------------------------------------------------------------
# Association tables for many-to-many relationships
# ---------------------------------------------------------------------------

niche_hf_models: Table = Table(
    "niche_hf_models",
    Base.metadata,
    Column(
        "niche_id",
        Integer,
        ForeignKey("niches.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "hf_model_id",
        Integer,
        ForeignKey("hf_models.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
    ),
    Column("confidence", Float, default=1.0),
)

niche_github_repos: Table = Table(
    "niche_github_repos",
    Base.metadata,
    Column(
        "niche_id",
        Integer,
        ForeignKey("niches.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "github_repo_id",
        Integer,
        ForeignKey("github_repos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
    ),
    Column("confidence", Float, default=1.0),
)

niche_arxiv_papers: Table = Table(
    "niche_arxiv_papers",
    Base.metadata,
    Column(
        "niche_id",
        Integer,
        ForeignKey("niches.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "arxiv_paper_id",
        Integer,
        ForeignKey("arxiv_papers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
    ),
    Column("confidence", Float, default=1.0),
)


# ---------------------------------------------------------------------------
# Niche model
# ---------------------------------------------------------------------------


class Niche(Base, TimestampMixin):
    """Represents a topic niche used to group related AI resources."""

    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # -- Many-to-many relationships ------------------------------------------

    hf_models: Mapped[list[HFModel]] = relationship(
        "HFModel",
        secondary=niche_hf_models,
        back_populates="niches",
        lazy="selectin",
    )
    github_repos: Mapped[list[GitHubRepo]] = relationship(
        "GitHubRepo",
        secondary=niche_github_repos,
        back_populates="niches",
        lazy="selectin",
    )
    arxiv_papers: Mapped[list[ArxivPaper]] = relationship(
        "ArxivPaper",
        secondary=niche_arxiv_papers,
        back_populates="niches",
        lazy="selectin",
    )

    # -- One-to-many relationships -------------------------------------------

    signals: Mapped[list[TrendSignal]] = relationship(
        "TrendSignal",
        back_populates="niche",
        lazy="selectin",
    )
    reports: Mapped[list[Report]] = relationship(
        "Report",
        back_populates="niche",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Niche(id={self.id}, slug='{self.slug}', is_active={self.is_active})>"
