"""Lever ATS provider — uses the public Postings API (no auth required)."""

from __future__ import annotations

import contextlib
import re
from datetime import UTC, datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from job_search_agent.config import get_settings
from job_search_agent.logging import get_logger
from job_search_agent.models.job import ATSProvider, Job
from job_search_agent.providers.base import JobProvider, ProviderResult, SearchQuery, matches_query
from job_search_agent.providers.greenhouse import (
    _detect_remote,
    _extract_experience,
    _extract_skills_from_text,
    _normalize_title,
)

logger = get_logger(__name__)

LEVER_API = "https://api.lever.co/v0/postings"


class LeverProvider(JobProvider):
    """Provider for Lever-hosted job boards.

    Uses the public API: GET https://api.lever.co/v0/postings/{company}?mode=json
    No authentication required.
    """

    def __init__(self, companies: list[str] | None = None):
        settings = get_settings()
        self.companies = companies or settings.lever_companies
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "lever"

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
        """Search across all configured Lever companies."""
        all_jobs: list[Job] = []
        errors: list[str] = []

        if not self.companies:
            return ProviderResult(
                provider_name=self.name,
                jobs=[],
                errors=["No Lever company slugs configured"],
            )

        for company in self.companies:
            try:
                jobs = await self._fetch_company(company, query)
                all_jobs.extend(jobs)
                logger.info("lever_company_fetched", company=company, count=len(jobs))
            except Exception as e:
                error_msg = f"Lever company '{company}': {e}"
                logger.error("lever_company_error", company=company, error=str(e))
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
    async def _fetch_company(self, company: str, query: SearchQuery) -> list[Job]:
        """Fetch jobs from a single Lever company."""
        url = f"{LEVER_API}/{company}"
        params = {"mode": "json"}

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list):
            return []

        jobs: list[Job] = []
        for raw_job in data:
            try:
                job = self._normalize(raw_job, company)
                if matches_query(job, query):
                    jobs.append(job)
            except Exception as e:
                logger.warning(
                    "lever_job_parse_error",
                    company=company,
                    job_id=raw_job.get("id"),
                    error=str(e),
                )

        return jobs

    def _normalize(self, raw: dict, company_slug: str) -> Job:
        """Normalize a raw Lever posting into canonical schema."""
        # Description
        desc_parts = []
        for section in raw.get("lists", []):
            if section.get("text"):
                desc_parts.append(section["text"])
            if section.get("content"):
                desc_parts.append(section["content"])

        desc_plain = raw.get("descriptionPlain", "")
        additional = raw.get("additionalPlain", "")
        full_description = f"{desc_plain}\n{additional}\n" + "\n".join(desc_parts)
        full_description = full_description.strip()

        # Skills
        required_skills, preferred_skills = _extract_skills_from_text(full_description)

        # Location
        location = raw.get("categories", {}).get("location", None)

        # Remote
        remote_type = _detect_remote(location or "", full_description)

        # Experience
        min_exp, max_exp = _extract_experience(full_description)

        # Timestamp
        posted_at = None
        created_at_ms = raw.get("createdAt")
        if created_at_ms:
            with contextlib.suppress(ValueError, OSError):
                posted_at = datetime.fromtimestamp(created_at_ms / 1000, tz=UTC)

        job_url = raw.get("hostedUrl", f"https://jobs.lever.co/{company_slug}/{raw.get('id', '')}")
        apply_url = raw.get("applyUrl", job_url)

        # Team/department
        team = raw.get("categories", {}).get("team", None)
        department = raw.get("categories", {}).get("department", None)

        return Job(
            external_id=raw.get("id"),
            company=company_slug.replace("-", " ").title(),
            title=raw.get("text", "Unknown"),
            normalized_title=_normalize_title(raw.get("text", "")),
            location=location,
            remote_type=remote_type,
            description=full_description if full_description else None,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            min_experience=min_exp,
            max_experience=max_exp,
            source="lever",
            source_url=job_url,
            canonical_url=job_url,
            application_url=apply_url,
            ats_provider=ATSProvider.LEVER,
            posted_at=posted_at,
            discovered_at=datetime.now(UTC),
            department=department,
            team=team,
        )

    async def fetch_job(self, job_url: str) -> Job | None:
        """Fetch a single job by its Lever URL."""
        # Format: https://jobs.lever.co/{company}/{id}
        match = re.search(r"jobs\.lever\.co/([\w-]+)/(\w+)", job_url)
        if not match:
            return None

        company = match.group(1)
        job_id = match.group(2)

        try:
            resp = await self.client.get(f"{LEVER_API}/{company}/{job_id}")
            resp.raise_for_status()
            raw = resp.json()
            return self._normalize(raw, company)
        except Exception as e:
            logger.error("lever_fetch_error", url=job_url, error=str(e))
            return None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
