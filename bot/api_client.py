"""Async HTTP client for communicating with the FastAPI backend."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger(__name__)


class BotAPIClient:
    """Wraps all HTTP calls to the AI Trend Monitor FastAPI backend.

    Instantiate with the base URL of the API (e.g. ``http://api:8000``)
    and call the async methods to retrieve data.  The underlying
    ``httpx.AsyncClient`` is reused across requests for connection
    pooling.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url: str = base_url.rstrip("/")
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, **params: object) -> dict:
        """Perform a GET request and return the JSON response body."""
        # Strip None values so optional params are not sent as "None"
        filtered_params = {k: v for k, v in params.items() if v is not None}
        logger.debug("api_get", path=path, params=filtered_params)
        response = await self._client.get(path, params=filtered_params)
        response.raise_for_status()
        return response.json()

    async def _post(self, path: str, **params: object) -> dict:
        """Perform a POST request and return the JSON response body."""
        filtered_params = {k: v for k, v in params.items() if v is not None}
        logger.debug("api_post", path=path, params=filtered_params)
        response = await self._client.post(path, params=filtered_params)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    async def get_overview(self) -> dict:
        """GET /api/overview/ -- dashboard summary."""
        return await self._get("/api/overview/")

    # ------------------------------------------------------------------
    # Niches
    # ------------------------------------------------------------------

    async def get_niches(self) -> list[dict]:
        """GET /api/niches/ -- list of niches with stats."""
        data = await self._get("/api/niches/")
        return data.get("niches", [])

    async def get_niche_detail(self, niche_id: int) -> dict:
        """GET /api/niches/{niche_id} -- single niche with models/repos."""
        return await self._get(f"/api/niches/{niche_id}")

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    async def search_models(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """GET /api/models/?search=... -- search models by name/tag."""
        data = await self._get(
            "/api/models/",
            search=query,
            per_page=limit,
        )
        return data.get("items", [])

    async def get_model(self, model_id: str) -> dict:
        """GET /api/models/{model_id} -- single model detail."""
        return await self._get(f"/api/models/{model_id}")

    async def get_top_models(
        self,
        limit: int = 10,
        sort_by: str = "growth",
    ) -> list[dict]:
        """GET /api/models/?sort_by=growth -- top models ranked by growth."""
        data = await self._get(
            "/api/models/",
            sort_by=sort_by,
            per_page=limit,
        )
        return data.get("items", [])

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    async def get_signals(
        self,
        severity: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """GET /api/signals/ -- recent signals, optionally filtered."""
        data = await self._get(
            "/api/signals/",
            severity=severity,
            limit=limit,
        )
        return data.get("signals", [])

    async def get_signal_stats(self) -> dict:
        """GET /api/signals/stats -- signal count breakdowns."""
        return await self._get("/api/signals/stats")

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    async def get_reports(self) -> list[dict]:
        """GET /api/reports/ -- list of generated reports."""
        data = await self._get("/api/reports/")
        return data.get("reports", [])

    async def generate_report(self, report_type: str = "daily") -> dict:
        """POST /api/reports/generate -- generate a new report."""
        return await self._post("/api/reports/generate", report_type=report_type)

    async def get_report(self, report_id: int) -> dict:
        """GET /api/reports/{id} -- fetch a specific report."""
        return await self._get(f"/api/reports/{report_id}")

    # ------------------------------------------------------------------
    # Settings / Admin
    # ------------------------------------------------------------------

    async def get_status(self) -> dict:
        """GET /api/settings/status -- system health check."""
        return await self._get("/api/settings/status")

    async def trigger_collection(self, source: str = "all") -> dict:
        """POST /api/settings/collect?source= -- start data collection."""
        return await self._post("/api/settings/collect", source=source)

    async def trigger_analytics(self) -> dict:
        """POST /api/settings/analyze -- start analytics pipeline."""
        return await self._post("/api/settings/analyze")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client gracefully."""
        await self._client.aclose()
        logger.info("api_client_closed")
