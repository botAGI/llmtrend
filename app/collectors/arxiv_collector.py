"""arXiv paper data collector.

Queries the arXiv Atom API for recent papers in configured categories
(e.g. ``cs.AI``, ``cs.LG``, ``cs.CL``), parses the XML responses, and
upserts each paper into the ``arxiv_papers`` table.  Polite delays between
requests are enforced via ``ARXIV_REQUEST_DELAY``.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
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
from app.models.arxiv_paper import ArxivPaper
from app.utils.helpers import utc_now

logger = structlog.get_logger(__name__)

_ARXIV_API_BASE = "http://export.arxiv.org/api/query"

# Atom XML namespaces used by the arXiv API.
_NS_ATOM = "http://www.w3.org/2005/Atom"
_NS_ARXIV = "http://arxiv.org/schemas/atom"

# Namespace map for ElementTree find/findall calls.
_NAMESPACES: dict[str, str] = {
    "atom": _NS_ATOM,
    "arxiv": _NS_ARXIV,
}


class ArxivCollector(BaseCollector):
    """Collector for academic papers from the arXiv preprint server.

    For each category listed in ``settings.ARXIV_CATEGORIES``, the collector
    fetches up to ``ARXIV_MAX_RESULTS`` papers sorted by submission date,
    parses the Atom XML feed, and upserts every paper by ``arxiv_id``.
    """

    SOURCE_TYPE = "arxiv"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._settings = get_settings()

    # ── HTTP plumbing ────────────────────────────────────────────────────

    async def get_client(self) -> httpx.AsyncClient:
        """Return the shared client with the arXiv-specific timeout."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(float(self._settings.ARXIV_REQUEST_TIMEOUT)),
                headers=self._get_headers(),
                follow_redirects=True,
            )
        return self._client

    # ── API fetching ─────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=3, min=3, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def _fetch_category(
        self,
        category: str,
        max_results: int,
    ) -> str:
        """Fetch the Atom XML feed for a single arXiv category.

        Args:
            category: arXiv category identifier (e.g. ``"cs.AI"``).
            max_results: Maximum number of results to request.

        Returns:
            The raw XML response body as a string.
        """
        client = await self.get_client()
        params: dict[str, Any] = {
            "search_query": f"cat:{category}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results,
        }

        self.log.info(
            "arxiv.fetch_category",
            category=category,
            max_results=max_results,
        )

        response = await client.get(_ARXIV_API_BASE, params=params)
        response.raise_for_status()

        self.log.info(
            "arxiv.fetch_category.done",
            category=category,
            response_length=len(response.text),
        )

        return response.text

    # ── XML parsing ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_datetime(text: str | None) -> datetime | None:
        """Parse an ISO 8601 datetime string from an Atom feed element."""
        if not text:
            return None
        try:
            cleaned = text.strip().replace("Z", "+00:00")
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_arxiv_id(id_url: str) -> str:
        """Extract the arxiv_id from the Atom ``<id>`` element.

        Example::

            "http://arxiv.org/abs/2403.12345v1" -> "2403.12345v1"

        The raw URL contains a leading ``http://arxiv.org/abs/`` prefix
        that is stripped to yield the compact identifier.
        """
        # Remove the common prefix.
        for prefix in ("http://arxiv.org/abs/", "https://arxiv.org/abs/"):
            if id_url.startswith(prefix):
                return id_url[len(prefix):]
        # Fallback: return the last path segment.
        return id_url.rsplit("/", 1)[-1]

    @staticmethod
    def _get_text(element: ET.Element | None) -> str | None:
        """Safely extract stripped text content from an XML element."""
        if element is None or element.text is None:
            return None
        text = element.text.strip()
        return text if text else None

    @staticmethod
    def _clean_whitespace(text: str | None) -> str | None:
        """Collapse internal whitespace and newlines into single spaces."""
        if not text:
            return text
        return " ".join(text.split())

    def _parse_entries(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse Atom XML into a list of paper data dicts.

        Args:
            xml_text: Raw XML response from the arXiv API.

        Returns:
            A list of dicts with fields matching :class:`ArxivPaper` columns.
        """
        papers: list[dict[str, Any]] = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            self.log.error("arxiv.xml_parse_error", error=str(exc))
            return papers

        entries = root.findall(f"{{{_NS_ATOM}}}entry")

        for entry in entries:
            try:
                paper = self._parse_single_entry(entry)
                if paper is not None:
                    papers.append(paper)
            except Exception as exc:
                self.log.error("arxiv.entry_parse_error", error=str(exc))

        return papers

    def _parse_single_entry(self, entry: ET.Element) -> dict[str, Any] | None:
        """Parse a single ``<entry>`` element into a paper dict.

        Returns ``None`` if the entry lacks a valid ID.
        """
        # -- ID ----------------------------------------------------------------
        id_elem = entry.find(f"{{{_NS_ATOM}}}id")
        id_url = self._get_text(id_elem)
        if not id_url:
            return None
        arxiv_id = self._extract_arxiv_id(id_url)

        # -- Title & abstract --------------------------------------------------
        title_raw = self._get_text(entry.find(f"{{{_NS_ATOM}}}title"))
        title = self._clean_whitespace(title_raw) or ""

        summary_raw = self._get_text(entry.find(f"{{{_NS_ATOM}}}summary"))
        abstract = self._clean_whitespace(summary_raw)

        # -- Authors -----------------------------------------------------------
        author_elements = entry.findall(f"{{{_NS_ATOM}}}author")
        authors: list[str] = []
        for author_elem in author_elements:
            name_elem = author_elem.find(f"{{{_NS_ATOM}}}name")
            name_text = self._get_text(name_elem)
            if name_text:
                authors.append(name_text)

        # -- Categories --------------------------------------------------------
        category_elements = entry.findall(f"{{{_NS_ATOM}}}category")
        categories: list[str] = []
        for cat_elem in category_elements:
            term = cat_elem.get("term")
            if term:
                categories.append(term)

        # -- Primary category (arXiv namespace) --------------------------------
        primary_cat_elem = entry.find(f"{{{_NS_ARXIV}}}primary_category")
        primary_category: str = ""
        if primary_cat_elem is not None:
            primary_category = primary_cat_elem.get("term", "")
        elif categories:
            primary_category = categories[0]

        # -- Links (pdf, abstract) ---------------------------------------------
        pdf_url: str | None = None
        abstract_url: str | None = None

        for link_elem in entry.findall(f"{{{_NS_ATOM}}}link"):
            link_title = link_elem.get("title", "")
            link_href = link_elem.get("href", "")
            link_type = link_elem.get("type", "")

            if link_title == "pdf":
                pdf_url = link_href
            elif link_type == "text/html" or link_elem.get("rel") == "alternate":
                abstract_url = link_href

        # -- arXiv-specific optional fields ------------------------------------
        comment = self._get_text(entry.find(f"{{{_NS_ARXIV}}}comment"))
        journal_ref = self._get_text(entry.find(f"{{{_NS_ARXIV}}}journal_ref"))
        doi = self._get_text(entry.find(f"{{{_NS_ARXIV}}}doi"))

        # -- Dates -------------------------------------------------------------
        published_raw = self._get_text(entry.find(f"{{{_NS_ATOM}}}published"))
        updated_raw = self._get_text(entry.find(f"{{{_NS_ATOM}}}updated"))

        published_at = self._parse_datetime(published_raw)
        updated_at_arxiv = self._parse_datetime(updated_raw)

        if published_at is None:
            # published_at is NOT NULL in the ORM, skip entries without it.
            self.log.warning(
                "arxiv.entry.no_published_date",
                arxiv_id=arxiv_id,
            )
            return None

        return {
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "categories": categories,
            "primary_category": primary_category,
            "pdf_url": pdf_url,
            "abstract_url": abstract_url,
            "comment": comment,
            "journal_ref": journal_ref,
            "doi": doi,
            "published_at": published_at,
            "updated_at_arxiv": updated_at_arxiv,
        }

    # ── Upsert logic ────────────────────────────────────────────────────

    async def _upsert_paper(
        self,
        data: dict[str, Any],
        result: CollectionResult,
    ) -> None:
        """Insert or update a single arXiv paper row.

        New papers are inserted with ``first_seen_at = now``.  Existing
        papers have their ``updated_at_arxiv`` field refreshed if the API
        reports a newer update timestamp.
        """
        now = utc_now()

        stmt = select(ArxivPaper).where(ArxivPaper.arxiv_id == data["arxiv_id"])
        row = (await self.session.execute(stmt)).scalar_one_or_none()

        if row is not None:
            # Only update if the arXiv update timestamp has advanced, or if
            # we never recorded one.
            if data["updated_at_arxiv"] is not None:
                row.updated_at_arxiv = data["updated_at_arxiv"]

            # Refresh metadata that may have changed on revision.
            row.title = data["title"]
            row.abstract = data["abstract"]
            row.authors = data["authors"]
            row.categories = data["categories"]
            row.primary_category = data["primary_category"]
            row.pdf_url = data["pdf_url"]
            row.abstract_url = data["abstract_url"]
            row.comment = data["comment"]
            row.journal_ref = data["journal_ref"]
            row.doi = data["doi"]

            result.items_updated += 1
        else:
            new_paper = ArxivPaper(
                arxiv_id=data["arxiv_id"],
                title=data["title"],
                abstract=data["abstract"],
                authors=data["authors"],
                categories=data["categories"],
                primary_category=data["primary_category"],
                pdf_url=data["pdf_url"],
                abstract_url=data["abstract_url"],
                comment=data["comment"],
                journal_ref=data["journal_ref"],
                doi=data["doi"],
                published_at=data["published_at"],
                updated_at_arxiv=data["updated_at_arxiv"],
                first_seen_at=now,
            )
            self.session.add(new_paper)
            result.items_created += 1

    # ── Main collection logic ────────────────────────────────────────────

    async def collect(self) -> CollectionResult:
        """Fetch papers across all configured arXiv categories and upsert them.

        The collector enforces a polite delay of ``ARXIV_REQUEST_DELAY``
        seconds between category queries to comply with arXiv's usage
        policy.  Papers that appear in multiple categories are deduplicated
        by ``arxiv_id``.

        Returns:
            A :class:`CollectionResult` with aggregate counts.
        """
        result = CollectionResult()
        categories = self._settings.ARXIV_CATEGORIES
        max_results = self._settings.ARXIV_MAX_RESULTS
        request_delay = self._settings.ARXIV_REQUEST_DELAY

        # Track seen arxiv_ids to avoid redundant upserts when a paper
        # belongs to multiple monitored categories.
        seen_ids: set[str] = set()

        for cat_idx, category in enumerate(categories):
            self.log.info(
                "arxiv.category.start",
                category=category,
                category_index=cat_idx + 1,
                total_categories=len(categories),
            )

            # Fetch XML feed for this category.
            try:
                xml_text = await self._fetch_category(category, max_results)
            except Exception as exc:
                self.log.error(
                    "arxiv.fetch.error",
                    category=category,
                    error=str(exc),
                )
                result.errors.append(
                    f"Failed to fetch category {category}: {exc}"
                )
                # Continue to the next category rather than aborting.
                if cat_idx < len(categories) - 1:
                    await asyncio.sleep(request_delay)
                continue

            # Parse entries from the XML.
            papers = self._parse_entries(xml_text)
            self.log.info(
                "arxiv.category.parsed",
                category=category,
                paper_count=len(papers),
            )

            # Upsert each paper.
            for paper_data in papers:
                arxiv_id = paper_data["arxiv_id"]

                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)

                result.items_fetched += 1

                try:
                    await self._upsert_paper(paper_data, result)
                except Exception as exc:
                    self.log.error(
                        "arxiv.upsert.error",
                        arxiv_id=arxiv_id,
                        error=str(exc),
                    )
                    result.errors.append(
                        f"Upsert failed for arxiv_id={arxiv_id}: {exc}"
                    )

            # Flush after each category to keep the session manageable.
            await self.session.flush()

            # Polite delay between category requests.
            if cat_idx < len(categories) - 1:
                self.log.debug(
                    "arxiv.delay",
                    delay_seconds=request_delay,
                )
                await asyncio.sleep(request_delay)

        self.log.info(
            "arxiv.collect.done",
            fetched=result.items_fetched,
            created=result.items_created,
            updated=result.items_updated,
            errors=len(result.errors),
        )

        return result
