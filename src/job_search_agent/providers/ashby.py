"""Ashby ATS provider — uses the public Posting API (no auth required)."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from job_search_agent.config import get_settings
from job_search_agent.logging import get_logger
from job_search_agent.models.job import ATSProvider, EmploymentType, Job, RemoteType
from job_search_agent.providers.base import JobProvider, ProviderResult, SearchQuery, matches_query
from job_search_agent.providers.greenhouse import (
    _detect_remote,
    _extract_experience,
    _extract_skills_from_text,
    _normalize_title,
    _strip_html,
)

logger = get_logger(__name__)

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board"


class AshbyProvider(JobProvider):
    """Provider for Ashby-hosted job boards.

    Uses: GET https://api.ashbyhq.com/posting-api/job-board/{board_name}
    No authentication required.
    """

    def __init__(self, boards: list[str] | None = None):
        settings = get_settings()
        self.boards = boards or settings.ashby_boards
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "ashby"

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            settings = get_settings()
            self._client = httpx.AsyncClient(
                timeout=settings.http_timeout_seconds,
                headers={"Accept": "application/json"},
                follow_redirects=True,
            )
        return self._client

    async def search(self, query: SearchQuery) -> ProviderResult:
        """Search across all configured Ashby boards."""
        all_jobs: list[Job] = []
        errors: list[str] = []

        if not self.boards:
            return ProviderResult(
                provider_name=self.name,
                jobs=[],
                errors=["No Ashby board names configured"],
            )

        for board in self.boards:
            try:
                jobs = await self._fetch_board(board, query)
                all_jobs.extend(jobs)
                logger.info("ashby_board_fetched", board=board, count=len(jobs))
            except Exception as e:
                error_msg = f"Ashby board '{board}': {e}"
                logger.error("ashby_board_error", board=board, error=str(e))
                errors.append(error_msg)

        if query.limit and len(all_jobs) > query.limit:
            all_jobs = all_jobs[: query.limit]

        return ProviderResult(
            provider_name=self.name,
            jobs=all_jobs,
            total_found=len(all_jobs),
            errors=errors,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _fetch_board(self, board: str, query: SearchQuery) -> list[Job]:
        """Fetch jobs from a single Ashby board."""
        url = f"{ASHBY_API}/{board}"
        params = {"includeCompensation": "true"}

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        jobs: list[Job] = []
        for raw_job in data.get("jobs", []):
            try:
                job = self._normalize(raw_job, board)
                if matches_query(job, query):
                    jobs.append(job)
            except Exception as e:
                logger.warning(
                    "ashby_job_parse_error",
                    board=board,
                    job_title=raw_job.get("title"),
                    error=str(e),
                )

        return jobs

    def _normalize(self, raw: dict, board_name: str) -> Job:
        """Normalize an Ashby job into canonical schema."""
        # Description
        desc_html = raw.get("descriptionHtml", "")
        description = _strip_html(desc_html) if desc_html else None

        # Skills
        required_skills, preferred_skills = _extract_skills_from_text(description or "")

        # Location
        location = raw.get("location")

        # Remote type
        workplace_type = raw.get("workplaceType", "").lower()
        if workplace_type == "remote":
            remote_type = RemoteType.REMOTE
        elif workplace_type == "hybrid":
            remote_type = RemoteType.HYBRID
        elif workplace_type in ("onsite", "on-site"):
            remote_type = RemoteType.ONSITE
        else:
            remote_type = _detect_remote(location or "", description or "")

        # Employment type
        emp_type_raw = raw.get("employmentType", "").lower()
        emp_map = {
            "fulltime": EmploymentType.FULL_TIME,
            "full-time": EmploymentType.FULL_TIME,
            "full_time": EmploymentType.FULL_TIME,
            "parttime": EmploymentType.PART_TIME,
            "part-time": EmploymentType.PART_TIME,
            "contract": EmploymentType.CONTRACT,
            "intern": EmploymentType.INTERNSHIP,
            "internship": EmploymentType.INTERNSHIP,
        }
        employment_type = emp_map.get(emp_type_raw, EmploymentType.UNKNOWN)

        # Experience
        min_exp, max_exp = _extract_experience(description or "")

        # Compensation
        salary_min = salary_max = salary_currency = None
        compensation = raw.get("compensation")
        if compensation and isinstance(compensation, dict):
            tiers = compensation.get("compensationTiers", [])
            if tiers:
                tier = tiers[0]
                salary_min = tier.get("min")
                salary_max = tier.get("max")
                salary_currency = tier.get("currency", "USD")

        # Timestamps
        posted_at = None
        if raw.get("publishedAt"):
            with contextlib.suppress(ValueError, AttributeError):
                posted_at = datetime.fromisoformat(raw["publishedAt"].replace("Z", "+00:00"))

        job_url = raw.get("jobUrl", "")
        apply_url = raw.get("applyUrl", job_url)

        return Job(
            external_id=raw.get("id"),
            company=board_name.replace("-", " ").title(),
            title=raw.get("title", "Unknown"),
            normalized_title=_normalize_title(raw.get("title", "")),
            location=location,
            remote_type=remote_type,
            employment_type=employment_type,
            description=description,
            description_html=desc_html if desc_html else None,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            min_experience=min_exp,
            max_experience=max_exp,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            source="ashby",
            source_url=job_url,
            canonical_url=job_url,
            application_url=apply_url,
            ats_provider=ATSProvider.ASHBY,
            posted_at=posted_at,
            discovered_at=datetime.now(UTC),
            department=raw.get("department"),
            team=raw.get("team"),
        )

    async def fetch_job(self, job_url: str) -> Job | None:
        """Fetch a single Ashby job by URL. Limited since Ashby has no single-job public endpoint."""
        logger.info("ashby_fetch_job_url", url=job_url)
        # Ashby doesn't have a public single-job API — we'd need to scrape
        # For now, return None and let the generic provider handle it
        return None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
