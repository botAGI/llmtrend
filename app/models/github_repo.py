"""ORM model for GitHub repositories tracked by the AI Trend Monitor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.niche import Niche


class GitHubRepo(Base, TimestampMixin):
    """Represents a GitHub repository related to AI/LLM development."""

    __tablename__ = "github_repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    owner_login: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_url: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    topics: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stars_previous: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    forks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    license_spdx: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    repo_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    repo_pushed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # -- Many-to-many back-reference ------------------------------------------

    niches: Mapped[list[Niche]] = relationship(
        "Niche",
        secondary="niche_github_repos",
        back_populates="github_repos",
        lazy="selectin",
    )

    @property
    def stars_growth_percent(self) -> Optional[float]:
        """Calculate percentage growth in stars compared to previous snapshot."""
        if self.stars_previous == 0:
            return None
        return ((self.stars - self.stars_previous) / self.stars_previous) * 100.0

    def __repr__(self) -> str:
        return f"<GitHubRepo(id={self.id}, full_name='{self.full_name}', stars={self.stars})>"
