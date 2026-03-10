"""HTTP client for communicating with the FastAPI backend."""

from __future__ import annotations

from typing import Any

import requests
import streamlit as st

from dashboard.config import API_BASE_URL


class APIError(Exception):
    """Raised when an API request fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


class DashboardAPI:
    """Thin wrapper around the FastAPI backend endpoints."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
        """Perform a GET request and return parsed JSON."""
        try:
            resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise APIError(0, "Cannot connect to API server. Is the backend running?")
        except requests.exceptions.Timeout:
            raise APIError(0, "API request timed out.")
        except requests.exceptions.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("detail", exc.response.text)
            except Exception:
                detail = exc.response.text
            raise APIError(exc.response.status_code, detail) from exc

    def _post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 60,
    ) -> dict[str, Any]:
        """Perform a POST request and return parsed JSON."""
        try:
            resp = self.session.post(
                f"{self.base_url}{path}", json=json, params=params, timeout=timeout
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise APIError(0, "Cannot connect to API server. Is the backend running?")
        except requests.exceptions.Timeout:
            raise APIError(0, "API request timed out.")
        except requests.exceptions.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("detail", exc.response.text)
            except Exception:
                detail = exc.response.text
            raise APIError(exc.response.status_code, detail) from exc

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    def get_overview(self) -> dict[str, Any]:
        """Fetch dashboard overview stats, trending models, recent signals."""
        return self._get("/api/overview/")

    def get_timeline(self, pipeline_tag: str | None = None) -> dict[str, Any]:
        """Fetch download timeline data, optionally filtered by pipeline_tag."""
        params: dict[str, Any] = {}
        if pipeline_tag:
            params["pipeline_tag"] = pipeline_tag
        return self._get("/api/overview/timeline", params=params or None)

    # ------------------------------------------------------------------
    # Niches
    # ------------------------------------------------------------------

    def get_niches(self) -> list[dict[str, Any]]:
        """Fetch all niches."""
        data = self._get("/api/niches/")
        return data.get("niches", [])

    def get_niche_detail(self, niche_id: int) -> dict[str, Any]:
        """Fetch detail for a single niche including models, repos, papers."""
        return self._get(f"/api/niches/{niche_id}")

    def analyze_niche(self, niche_id: int) -> dict[str, Any]:
        """Trigger AI analysis for a niche."""
        return self._post(f"/api/niches/{niche_id}/analyze", timeout=120)

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    def get_models(
        self,
        search: str | None = None,
        pipeline_tag: str | None = None,
        author: str | None = None,
        sort_by: str | None = None,
        order: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """Fetch paginated HuggingFace models."""
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if search:
            params["search"] = search
        if pipeline_tag:
            params["pipeline_tag"] = pipeline_tag
        if author:
            params["author"] = author
        if sort_by:
            params["sort_by"] = sort_by
        if order:
            params["order"] = order
        return self._get("/api/models/", params=params)

    def get_github_repos(
        self,
        search: str | None = None,
        language: str | None = None,
        sort_by: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """Fetch paginated GitHub repositories."""
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if search:
            params["search"] = search
        if language:
            params["language"] = language
        if sort_by:
            params["sort_by"] = sort_by
        return self._get("/api/models/github", params=params)

    def get_model_detail(self, model_id: str) -> dict[str, Any]:
        """Fetch detail for a single model."""
        return self._get(f"/api/models/{model_id}")

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def get_signals(
        self,
        severity: str | None = None,
        signal_type: str | None = None,
        source_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Fetch signals with optional filters."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if severity:
            params["severity"] = severity
        if signal_type:
            params["signal_type"] = signal_type
        if source_type:
            params["source_type"] = source_type
        return self._get("/api/signals/", params=params)

    def get_signal_stats(self) -> dict[str, Any]:
        """Fetch signal statistics."""
        return self._get("/api/signals/stats")

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_reports(
        self,
        report_type: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Fetch list of reports."""
        params: dict[str, Any] = {"limit": limit}
        if report_type:
            params["report_type"] = report_type
        return self._get("/api/reports/", params=params)

    def generate_report(
        self,
        report_type: str = "general",
        niche_id: int | None = None,
    ) -> dict[str, Any]:
        """Trigger report generation."""
        payload: dict[str, Any] = {"report_type": report_type}
        if niche_id is not None:
            payload["niche_id"] = niche_id
        return self._post("/api/reports/generate", json=payload, timeout=120)

    def get_report_detail(self, report_id: int) -> dict[str, Any]:
        """Fetch a single report."""
        return self._get(f"/api/reports/{report_id}")

    # ------------------------------------------------------------------
    # Settings / Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Fetch system status (DB, Ollama, collections, env)."""
        return self._get("/api/settings/status")

    def trigger_collection(self, source: str = "all") -> dict[str, Any]:
        """Trigger data collection for a specific source or all sources."""
        return self._post("/api/settings/collect", params={"source": source}, timeout=120)

    def trigger_analytics(self) -> dict[str, Any]:
        """Trigger the analytics pipeline."""
        return self._post("/api/settings/analyze", timeout=120)


@st.cache_resource
def get_api() -> DashboardAPI:
    """Return a cached singleton API client instance."""
    return DashboardAPI(API_BASE_URL)
