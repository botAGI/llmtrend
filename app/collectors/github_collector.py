"""GitHub repository data collector.

Searches the GitHub Search API for repositories tagged with AI/ML-related
topics, paginates through results, and upserts each repository into the
``github_repos`` table.  Rate limits are respected by inspecting the
``X-RateLimit-Remaining`` response header and sleeping when necessary.
"""

from __future__ import annotations

import asyncio
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
from app.models.github_repo import GitHubRepo
from app.utils.helpers import utc_now

logger = structlog.get_logger(__name__)

_GITHUB_API_BASE = "https://api.github.com"

SEARCH_TOPICS: list[str] = [
    "large-language-model",
    "llm",
    "diffusion-model",
    "text-to-image",
    "text-generation",
    "transformers",
    "computer-vision",
    "speech-recognition",
    "reinforcement-learning",
    "mlops",
    "model-serving",
    "fine-tuning",
    "rag",
    "ai-agent",
    "multimodal",
    "text-to-speech",
    "text-to-video",
]


class GitHubCollector(BaseCollector):
    """Collector for GitHub repositories in AI/ML topics.

    For each topic in :data:`SEARCH_TOPICS`, the collector queries the GitHub
    Search API, paginates up to ``GITHUB_MAX_PAGES``, and upserts every
    repository whose star count meets ``GITHUB_MIN_STARS``.  Previous star
    counts are preserved in ``stars_previous`` for growth tracking.
    """

    SOURCE_TYPE = "github"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._settings = get_settings()

    # ── HTTP plumbing ────────────────────────────────────────────────────

    def _get_headers(self) -> dict[str, str]:
        """Include GitHub auth token and API version headers."""
        headers: dict[str, str] = {
            "User-Agent": "AITrendMonitor/1.0",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {self._settings.GITHUB_TOKEN}"
        return headers

    async def get_client(self) -> httpx.AsyncClient:
        """Return the shared client with the GitHub-specific timeout."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(float(self._settings.GITHUB_REQUEST_TIMEOUT)),
                headers=self._get_headers(),
                follow_redirects=True,
            )
        return self._client

    # ── Rate-limit handling ──────────────────────────────────────────────

    async def _respect_rate_limit(self, response: httpx.Response) -> None:
        """Inspect GitHub rate-limit headers and sleep when nearly exhausted.

        GitHub's Search API is limited to 30 requests per minute for
        authenticated users (10 for unauthenticated).  When
        ``X-RateLimit-Remaining`` drops to zero the collector sleeps until
        the reset time indicated by ``X-RateLimit-Reset``.
        """
        remaining_str = response.headers.get("X-RateLimit-Remaining")
        reset_str = response.headers.get("X-RateLimit-Reset")

        if remaining_str is None or reset_str is None:
            return

        remaining = int(remaining_str)
        reset_at = int(reset_str)

        if remaining <= 1:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            sleep_seconds = max(reset_at - now_ts + 1, 1)
            self.log.warning(
                "github.rate_limit.sleeping",
                remaining=remaining,
                sleep_seconds=sleep_seconds,
            )
            await asyncio.sleep(sleep_seconds)
        elif remaining <= 5:
            # Slow down proactively when approaching the limit.
            self.log.info(
                "github.rate_limit.low",
                remaining=remaining,
            )
            await asyncio.sleep(2.0)

    # ── API fetching ─────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=2, min=2, max=120),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _search_repositories(
        self,
        topic: str,
        page: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Execute a single page of the GitHub search query for *topic*.

        Args:
            topic: The repository topic to search for.
            page: 1-based page number.

        Returns:
            A tuple of (list of raw repo dicts, has_more_pages).
        """
        client = await self.get_client()
        min_stars = self._settings.GITHUB_MIN_STARS
        per_page = self._settings.GITHUB_RESULTS_PER_PAGE
        query = f"topic:{topic} stars:>={min_stars}"

        params: dict[str, Any] = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": page,
        }

        self.log.debug(
            "github.search",
            topic=topic,
            page=page,
            min_stars=min_stars,
        )

        response = await client.get(
            f"{_GITHUB_API_BASE}/search/repositories",
            params=params,
        )
        response.raise_for_status()
        await self._respect_rate_limit(response)

        body: dict[str, Any] = response.json()
        items: list[dict[str, Any]] = body.get("items", [])
        total_count: int = body.get("total_count", 0)

        # GitHub caps search results at 1000 items.
        has_more = (page * per_page) < min(total_count, 1000)

        self.log.debug(
            "github.search.page_done",
            topic=topic,
            page=page,
            items_on_page=len(items),
            total_count=total_count,
        )

        return items, has_more

    # ── Data transformation ──────────────────────────────────────────────

    @staticmethod
    def _parse_datetime(raw: str | None) -> datetime | None:
        """Parse an ISO 8601 datetime string from the GitHub API."""
        if not raw:
            return None
        try:
            cleaned = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_repo_data(raw: dict[str, Any]) -> dict[str, Any]:
        """Transform a raw GitHub API repo dict into kwargs for :class:`GitHubRepo`."""
        owner: dict[str, Any] = raw.get("owner", {})
        license_info: dict[str, Any] | None = raw.get("license")
        license_spdx: str | None = None
        if license_info and isinstance(license_info, dict):
            license_spdx = license_info.get("spdx_id")
            # GitHub returns "NOASSERTION" when it can't identify the license.
            if license_spdx == "NOASSERTION":
                license_spdx = None

        return {
            "github_id": int(raw["id"]),
            "full_name": raw.get("full_name", ""),
            "name": raw.get("name", ""),
            "owner_login": owner.get("login", ""),
            "description": raw.get("description"),
            "html_url": raw.get("html_url", ""),
            "language": raw.get("language"),
            "topics": raw.get("topics", []) or [],
            "stars": int(raw.get("stargazers_count", 0)),
            "forks": int(raw.get("forks_count", 0)),
            "open_issues": int(raw.get("open_issues_count", 0)),
            "license_spdx": license_spdx,
            "repo_created_at": GitHubCollector._parse_datetime(raw.get("created_at")),
            "repo_pushed_at": GitHubCollector._parse_datetime(raw.get("pushed_at")),
        }

    # ── Upsert logic ────────────────────────────────────────────────────

    async def _upsert_repo(
        self,
        data: dict[str, Any],
        result: CollectionResult,
    ) -> None:
        """Insert or update a single GitHub repository row.

        Matches on ``github_id``.  When updating, the current star count is
        shifted to ``stars_previous``.
        """
        now = utc_now()

        stmt = select(GitHubRepo).where(GitHubRepo.github_id == data["github_id"])
        row = (await self.session.execute(stmt)).scalar_one_or_none()

        if row is not None:
            row.stars_previous = row.stars

            row.full_name = data["full_name"]
            row.name = data["name"]
            row.owner_login = data["owner_login"]
            row.description = data["description"]
            row.html_url = data["html_url"]
            row.language = data["language"]
            row.topics = data["topics"]
            row.stars = data["stars"]
            row.forks = data["forks"]
            row.open_issues = data["open_issues"]
            row.license_spdx = data["license_spdx"]
            row.repo_created_at = data["repo_created_at"]
            row.repo_pushed_at = data["repo_pushed_at"]
            row.last_seen_at = now

            result.items_updated += 1
        else:
            new_repo = GitHubRepo(
                github_id=data["github_id"],
                full_name=data["full_name"],
                name=data["name"],
                owner_login=data["owner_login"],
                description=data["description"],
                html_url=data["html_url"],
                language=data["language"],
                topics=data["topics"],
                stars=data["stars"],
                stars_previous=0,
                forks=data["forks"],
                open_issues=data["open_issues"],
                license_spdx=data["license_spdx"],
                repo_created_at=data["repo_created_at"],
                repo_pushed_at=data["repo_pushed_at"],
                first_seen_at=now,
                last_seen_at=now,
            )
            self.session.add(new_repo)
            result.items_created += 1

    # ── Main collection logic ────────────────────────────────────────────

    async def collect(self) -> CollectionResult:
        """Iterate over all search topics, paginate, and upsert repositories.

        The collector maintains a ``seen`` set of ``github_id`` values to
        deduplicate repos that appear under multiple topics.  A 2-second
        pause is inserted between topic searches to stay within GitHub's
        30 requests/minute search rate limit.

        Returns:
            A :class:`CollectionResult` with aggregate counts.
        """
        result = CollectionResult()
        max_pages = self._settings.GITHUB_MAX_PAGES

        # Track seen github_ids to avoid redundant upserts when a repo
        # matches multiple topic queries.
        seen_ids: set[int] = set()

        for topic_idx, topic in enumerate(SEARCH_TOPICS):
            self.log.info(
                "github.topic.start",
                topic=topic,
                topic_index=topic_idx + 1,
                total_topics=len(SEARCH_TOPICS),
            )

            for page in range(1, max_pages + 1):
                try:
                    items, has_more = await self._search_repositories(topic, page)
                except httpx.HTTPStatusError as exc:
                    # 422 often means the query is too complex or results
                    # are exhausted; 403 means rate-limited despite retries.
                    self.log.error(
                        "github.search.error",
                        topic=topic,
                        page=page,
                        status_code=exc.response.status_code,
                        error=str(exc),
                    )
                    result.errors.append(
                        f"Search failed for topic={topic} page={page}: "
                        f"HTTP {exc.response.status_code}"
                    )
                    break
                except Exception as exc:
                    self.log.error(
                        "github.search.error",
                        topic=topic,
                        page=page,
                        error=str(exc),
                    )
                    result.errors.append(
                        f"Search failed for topic={topic} page={page}: {exc}"
                    )
                    break

                if not items:
                    break

                for raw_item in items:
                    github_id = int(raw_item.get("id", 0))
                    if github_id in seen_ids:
                        continue
                    seen_ids.add(github_id)

                    result.items_fetched += 1

                    try:
                        data = self._extract_repo_data(raw_item)
                        await self._upsert_repo(data, result)
                    except Exception as exc:
                        self.log.error(
                            "github.upsert.error",
                            github_id=github_id,
                            error=str(exc),
                        )
                        result.errors.append(
                            f"Upsert failed for github_id={github_id}: {exc}"
                        )

                if not has_more:
                    break

                # Brief pause between pages within the same topic.
                await asyncio.sleep(1.0)

            # Flush after each topic to avoid accumulating too many dirty
            # objects in the session identity map.
            await self.session.flush()

            # Pause between topics to stay within rate limits.
            if topic_idx < len(SEARCH_TOPICS) - 1:
                await asyncio.sleep(2.0)

        self.log.info(
            "github.collect.done",
            fetched=result.items_fetched,
            created=result.items_created,
            updated=result.items_updated,
            errors=len(result.errors),
        )

        return result
