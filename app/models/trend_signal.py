"""ORM model for trend signals detected by the AI Trend Monitor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.niche import Niche


class TrendSignal(Base):
    """Represents a detected trend signal from any monitored source."""

    __tablename__ = "trend_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    signal_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium"
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    niche_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("niches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # -- Relationships -------------------------------------------------------

    niche: Mapped[Optional[Niche]] = relationship(
        "Niche",
        back_populates="signals",
    )

    def __repr__(self) -> str:
        return (
            f"<TrendSignal(id={self.id}, signal_type='{self.signal_type}', "
            f"source_type='{self.source_type}', severity='{self.severity}')>"
        )
