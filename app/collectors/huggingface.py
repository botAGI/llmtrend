"""Hugging Face Hub data collector.

Fetches models from the Hugging Face REST API, combining results sorted by
download count and trending score to capture both established and emerging
models.  Each model is upserted into the ``hf_models`` table, preserving
previous download and like counts for growth analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.collectors.base import BaseCollector, CollectionResult
from app.config import get_settings
from app.models.hf_model import HFModel
from app.utils.helpers import utc_now

logger = structlog.get_logger(__name__)

_HF_API_BASE = "https://huggingface.co/api"


class HuggingFaceCollector(BaseCollector):
    """Collector for Hugging Face Hub models.

    Queries the public REST API for the most-downloaded and most-trending
    models, merges the two result sets by ``model_id``, and upserts every
    model into the database.
    """

    SOURCE_TYPE = "huggingface"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._settings = get_settings()

    # ── HTTP plumbing ────────────────────────────────────────────────────

    def _get_headers(self) -> dict[str, str]:
        """Include Bearer auth when a HuggingFace token is configured."""
        headers: dict[str, str] = {"User-Agent": "AITrendMonitor/1.0"}
        if self._settings.HUGGINGFACE_TOKEN:
            headers["Authorization"] = f"Bearer {self._settings.HUGGINGFACE_TOKEN}"
        return headers

    async def get_client(self) -> httpx.AsyncClient:
        """Return the shared client with the HF-specific timeout."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(float(self._settings.HF_REQUEST_TIMEOUT)),
                headers=self._get_headers(),
                follow_redirects=True,
            )
        return self._client

    # ── API fetching ─────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _fetch_models(
        self,
        sort: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch a page of models from the HuggingFace API.

        Args:
            sort: Sort field (``"downloads"`` or ``"trending"``).
            limit: Maximum number of results to return.

        Returns:
            A list of raw JSON dicts from the API response.
        """
        client = await self.get_client()
        url = f"{_HF_API_BASE}/models"
        params: dict[str, Any] = {
            "sort": sort,
            "direction": "-1",
            "limit": limit,
        }

        self.log.info(
            "hf.fetch_models",
            sort=sort,
            limit=limit,
        )

        response = await client.get(url, params=params)
        response.raise_for_status()

        models: list[dict[str, Any]] = response.json()
        self.log.info(
            "hf.fetch_models.done",
            sort=sort,
            count=len(models),
        )
        return models

    # ── Data transformation ──────────────────────────────────────────────

    @staticmethod
    def _parse_last_modified(raw: str | None) -> datetime | None:
        """Parse an ISO datetime string from the HF API into a tz-aware datetime."""
        if not raw:
            return None
        try:
            # The API returns ISO 8601, possibly with a trailing Z or +00:00.
            cleaned = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_model_data(raw: dict[str, Any]) -> dict[str, Any]:
        """Transform a raw API dict into kwargs suitable for :class:`HFModel`.

        The API returns ``id`` for what we store as ``model_id``, and
        ``trendingScore`` (camelCase) for the trending metric.
        """
        model_id: str = raw.get("id", raw.get("modelId", ""))
        author: str | None = raw.get("author")

        # Derive name: strip author prefix if present.
        name = model_id
        if author and model_id.startswith(f"{author}/"):
            name = model_id[len(author) + 1 :]

        trending_score: float | None = raw.get("trendingScore", raw.get("trending_score"))

        last_modified_raw: str | None = raw.get("lastModified", raw.get("last_modified"))
        last_modified = HuggingFaceCollector._parse_last_modified(last_modified_raw)

        return {
            "model_id": model_id,
            "name": name,
            "author": author,
            "pipeline_tag": raw.get("pipeline_tag") or raw.get("pipelineTag"),
            "library_name": raw.get("library_name") or raw.get("libraryName"),
            "tags": raw.get("tags", []) or [],
            "downloads": int(raw.get("downloads", 0)),
            "likes": int(raw.get("likes", 0)),
            "trending_score": float(trending_score) if trending_score is not None else None,
            "is_private": bool(raw.get("private", False)),
            "last_modified": last_modified,
        }

    # ── Upsert logic ────────────────────────────────────────────────────

    async def _upsert_model(
        self,
        data: dict[str, Any],
        result: CollectionResult,
    ) -> None:
        """Insert or update a single HF model row.

        If the model already exists (matched by ``model_id``), the previous
        download and like counts are shifted into ``downloads_previous`` and
        ``likes_previous`` before the current values are written.
        """
        now = utc_now()

        stmt = select(HFModel).where(HFModel.model_id == data["model_id"])
        row = (await self.session.execute(stmt)).scalar_one_or_none()

        if row is not None:
            # Shift current values into *_previous columns.
            row.downloads_previous = row.downloads
            row.likes_previous = row.likes

            # Update mutable fields.
            row.name = data["name"]
            row.author = data["author"]
            row.pipeline_tag = data["pipeline_tag"]
            row.library_name = data["library_name"]
            row.tags = data["tags"]
            row.downloads = data["downloads"]
            row.likes = data["likes"]
            row.trending_score = data["trending_score"]
            row.is_private = data["is_private"]
            row.last_modified = data["last_modified"]
            row.last_seen_at = now

            result.items_updated += 1
        else:
            new_model = HFModel(
                model_id=data["model_id"],
                name=data["name"],
                author=data["author"],
                pipeline_tag=data["pipeline_tag"],
                library_name=data["library_name"],
                tags=data["tags"],
                downloads=data["downloads"],
                downloads_previous=0,
                likes=data["likes"],
                likes_previous=0,
                trending_score=data["trending_score"],
                is_private=data["is_private"],
                last_modified=data["last_modified"],
                first_seen_at=now,
                last_seen_at=now,
            )
            self.session.add(new_model)
            result.items_created += 1

    # ── Main collection logic ────────────────────────────────────────────

    async def collect(self) -> CollectionResult:
        """Fetch, merge, and upsert HuggingFace models.

        Steps:

        1. Fetch models sorted by downloads (limit from settings).
        2. Fetch models sorted by trending score (limit 500).
        3. Merge the two lists into a deduplicated dict keyed by ``model_id``.
           When a model appears in both lists the trending-sorted entry wins
           because it carries a meaningful ``trendingScore``.
        4. Upsert each model into the database.

        Returns:
            A :class:`CollectionResult` with aggregate counts.
        """
        result = CollectionResult()

        # -- Step 1: Fetch by downloads ----------------------------------------
        try:
            downloads_raw = await self._fetch_models(
                sort="downloads",
                limit=self._settings.HF_MODELS_LIMIT,
            )
        except Exception as exc:
            self.log.error("hf.fetch_downloads.error", error=str(exc))
            result.errors.append(f"Failed to fetch models by downloads: {exc}")
            downloads_raw = []

        # -- Step 2: Fetch by trending -----------------------------------------
        try:
            trending_raw = await self._fetch_models(
                sort="trending",
                limit=500,
            )
        except Exception as exc:
            self.log.error("hf.fetch_trending.error", error=str(exc))
            result.errors.append(f"Failed to fetch models by trending: {exc}")
            trending_raw = []

        # -- Step 3: Merge unique models by model_id ---------------------------
        # Start with downloads-sorted, then overlay trending-sorted so that
        # entries fetched from the trending endpoint (which carry the real
        # trendingScore) take precedence.
        merged: dict[str, dict[str, Any]] = {}

        for raw_item in downloads_raw:
            data = self._extract_model_data(raw_item)
            model_id = data["model_id"]
            if model_id:
                merged[model_id] = data

        for raw_item in trending_raw:
            data = self._extract_model_data(raw_item)
            model_id = data["model_id"]
            if model_id:
                if model_id in merged:
                    # Preserve the higher download count from the downloads
                    # endpoint but use the trending score from the trending
                    # endpoint.
                    existing = merged[model_id]
                    if data.get("trending_score") is not None:
                        existing["trending_score"] = data["trending_score"]
                else:
                    merged[model_id] = data

        result.items_fetched = len(merged)

        if not merged:
            self.log.warning("hf.no_models_fetched")
            return result

        # -- Step 4: Upsert into DB --------------------------------------------
        self.log.info("hf.upserting", count=len(merged))

        for model_id, data in merged.items():
            try:
                await self._upsert_model(data, result)
            except Exception as exc:
                self.log.error(
                    "hf.upsert.error",
                    model_id=model_id,
                    error=str(exc),
                )
                result.errors.append(f"Upsert failed for {model_id}: {exc}")

        # Flush all pending changes in a single round-trip.
        await self.session.flush()

        self.log.info(
            "hf.collect.done",
            fetched=result.items_fetched,
            created=result.items_created,
            updated=result.items_updated,
            errors=len(result.errors),
        )

        return result
