"""Abstract base collector for all data source collectors.

Every concrete collector (HuggingFace, GitHub, arXiv) inherits from
:class:`BaseCollector` and implements the :meth:`collect` coroutine.  The base
class manages the shared ``httpx.AsyncClient`` lifecycle, provides structured
logging, and records each run as a :class:`CollectionRun` row for observability.
"""

from __future__ import annotations

import abc
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection_run import CollectionRun
from app.utils.helpers import utc_now

logger = structlog.get_logger(__name__)


class CollectionResult:
    """Lightweight value object that captures the outcome of a single collection run.

    Attributes:
        items_fetched: Total items returned by the remote API.
        items_created: New rows inserted into the database.
        items_updated: Existing rows updated with fresh data.
        errors: Human-readable error messages accumulated during the run.
    """

    def __init__(self) -> None:
        self.items_fetched: int = 0
        self.items_created: int = 0
        self.items_updated: int = 0
        self.errors: list[str] = []

    @property
    def has_errors(self) -> bool:
        """Return ``True`` if any errors were recorded."""
        return len(self.errors) > 0

    @property
    def error_summary(self) -> str | None:
        """Return a single string summarising all recorded errors, or ``None``."""
        if not self.errors:
            return None
        return "; ".join(self.errors[:10])  # cap at 10 to avoid huge messages

    def __repr__(self) -> str:
        return (
            f"<CollectionResult(fetched={self.items_fetched}, "
            f"created={self.items_created}, updated={self.items_updated}, "
            f"errors={len(self.errors)})>"
        )


class BaseCollector(abc.ABC):
    """Abstract base for all data source collectors.

    Subclasses **must** define the ``SOURCE_TYPE`` class attribute and implement
    :meth:`collect`.  The base class provides:

    * A lazily-initialised ``httpx.AsyncClient`` with sensible defaults.
    * Structured logging bound to the source type.
    * :meth:`run` -- a top-level orchestrator that wraps :meth:`collect` with
      timing, error handling, and persistence of a :class:`CollectionRun` row.
    """

    SOURCE_TYPE: str  # override in every subclass

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._client: httpx.AsyncClient | None = None
        self.log = logger.bind(source_type=self.SOURCE_TYPE)

    # ── HTTP client management ───────────────────────────────────────────

    async def get_client(self) -> httpx.AsyncClient:
        """Return the shared async HTTP client, creating it on first access."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers=self._get_headers(),
                follow_redirects=True,
            )
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Return default HTTP headers.  Override to add auth tokens."""
        return {"User-Agent": "AITrendMonitor/1.0"}

    async def close(self) -> None:
        """Close the underlying HTTP client, releasing connection pools."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Main entry point ─────────────────────────────────────────────────

    async def run(self) -> CollectionResult:
        """Execute a full collection cycle with observability.

        This method:

        1. Records a ``CollectionRun`` row with status ``"running"``.
        2. Delegates to the subclass :meth:`collect` implementation.
        3. On success, updates the row to ``"completed"`` with timing data.
        4. On failure, updates the row to ``"failed"`` with the error message.
        5. Always closes the HTTP client in a ``finally`` block.

        Returns:
            A :class:`CollectionResult` with aggregate statistics.
        """
        started_at = utc_now()
        run_record = CollectionRun(
            source_type=self.SOURCE_TYPE,
            status="running",
            started_at=started_at,
        )
        self.session.add(run_record)
        await self.session.flush()

        self.log.info("collection.started")
        result = CollectionResult()

        try:
            result = await self.collect()

            completed_at = utc_now()
            duration = (completed_at - started_at).total_seconds()

            run_record.status = "completed" if not result.has_errors else "partial"
            run_record.items_fetched = result.items_fetched
            run_record.items_created = result.items_created
            run_record.items_updated = result.items_updated
            run_record.error_message = result.error_summary
            run_record.completed_at = completed_at
            run_record.duration_seconds = duration

            await self.session.flush()

            self.log.info(
                "collection.finished",
                status=run_record.status,
                items_fetched=result.items_fetched,
                items_created=result.items_created,
                items_updated=result.items_updated,
                duration_seconds=round(duration, 2),
                error_count=len(result.errors),
            )

        except Exception as exc:
            completed_at = utc_now()
            duration = (completed_at - started_at).total_seconds()

            run_record.status = "failed"
            run_record.error_message = str(exc)[:2000]
            run_record.completed_at = completed_at
            run_record.duration_seconds = duration

            await self.session.flush()

            self.log.error(
                "collection.failed",
                error=str(exc),
                duration_seconds=round(duration, 2),
                exc_info=True,
            )
            raise

        finally:
            await self.close()

        return result

    # ── Abstract interface ───────────────────────────────────────────────

    @abc.abstractmethod
    async def collect(self) -> CollectionResult:
        """Run the collection process.  Implemented by each concrete collector.

        Returns:
            A :class:`CollectionResult` with statistics about the run.
        """
        ...
