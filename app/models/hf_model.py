"""ORM model for Hugging Face models tracked by the AI Trend Monitor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.niche import Niche


class HFModel(Base, TimestampMixin):
    """Represents a model hosted on Hugging Face Hub."""

    __tablename__ = "hf_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, index=True
    )
    pipeline_tag: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    library_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    downloads: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    downloads_previous: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    likes_previous: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trending_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_modified: Mapped[Optional[datetime]] = mapped_column(
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
        secondary="niche_hf_models",
        back_populates="hf_models",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_hf_models_model_id", "model_id"),
    )

    @property
    def downloads_growth_percent(self) -> Optional[float]:
        """Calculate percentage growth in downloads compared to previous snapshot."""
        if self.downloads_previous == 0:
            return None
        return ((self.downloads - self.downloads_previous) / self.downloads_previous) * 100.0

    @property
    def likes_growth_percent(self) -> Optional[float]:
        """Calculate percentage growth in likes compared to previous snapshot."""
        if self.likes_previous == 0:
            return None
        return ((self.likes - self.likes_previous) / self.likes_previous) * 100.0

    def __repr__(self) -> str:
        return f"<HFModel(id={self.id}, model_id='{self.model_id}', downloads={self.downloads})>"
