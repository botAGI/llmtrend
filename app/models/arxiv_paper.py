"""ORM model for arXiv papers tracked by the AI Trend Monitor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.niche import Niche


class ArxivPaper(Base, TimestampMixin):
    """Represents an academic paper from arXiv in AI/ML categories."""

    __tablename__ = "arxiv_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    arxiv_id: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    authors: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    categories: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    primary_category: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    abstract_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    journal_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    updated_at_arxiv: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # -- Many-to-many back-reference ------------------------------------------

    niches: Mapped[list[Niche]] = relationship(
        "Niche",
        secondary="niche_arxiv_papers",
        back_populates="arxiv_papers",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ArxivPaper(id={self.id}, arxiv_id='{self.arxiv_id}', title='{self.title[:60]}...')>"
