"""ORM model for generated reports in the AI Trend Monitor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.niche import Niche


class Report(Base):
    """Represents a generated trend report (daily summary, weekly, deep-dive, etc.)."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    report_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    niche_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("niches.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    signals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    generation_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    llm_model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # -- Relationships -------------------------------------------------------

    niche: Mapped[Optional[Niche]] = relationship(
        "Niche",
        back_populates="reports",
    )

    def __repr__(self) -> str:
        return (
            f"<Report(id={self.id}, report_type='{self.report_type}', "
            f"title='{self.title[:60]}')>"
        )
