"""Adzuna job-search provider."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

import httpx

from job_search_agent.config import get_settings
from job_search_agent.models.job import ATSProvider, EmploymentType, Job
from job_search_agent.providers.base import JobProvider, ProviderResult, SearchQuery, matches_query
from job_search_agent.providers.greenhouse import (
    _detect_remote,
    _extract_experience,
    _extract_skills_from_text,
    _normalize_title,
)

API = "https://api.adzuna.com/v1/api/jobs"


class AdzunaProvider(JobProvider):
    """Search Adzuna's aggregated listings, primarily for India."""

    def __init__(self) -> None:
        settings = get_settings()
        self.app_id = settings.adzuna_app_id
        self.app_key = settings.adzuna_app_key
        self.country = settings.adzuna_country
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "adzuna"

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=get_settings().http_timeout_seconds,
                headers={"Accept": "application/json"},
                follow_redirects=True,
            )
        return self._client

    async def search(self, query: SearchQuery) -> ProviderResult:
        if not self.app_id or not self.app_key:
            return ProviderResult(provider_name=self.name)

        jobs: dict[str, Job] = {}
        errors: list[str] = []
        terms = query.roles or query.keywords or ["AI Engineer"]

        for term in terms:
            try:
                params: dict[str, str | int] = {
                    "app_id": self.app_id,
                    "app_key": self.app_key,
                    "what": term,
                    "results_per_page": min(query.limit, 50),
                    "sort_by": "date",
                    "content-type": "application/json",
                }
                if query.location and query.location.lower() not in {"india", "remote"}:
                    params["where"] = query.location
                if query.posted_within_hours is not None:
                    params["max_days_old"] = max(1, (query.posted_within_hours + 23) // 24)

                response = await self.client.get(
                    f"{API}/{self.country}/search/1",
                    params=params,
                )
                response.raise_for_status()
                for raw in response.json().get("results", []):
                    job = self._normalize(raw)
                    if matches_query(job, query):
                        jobs[job.external_id or job.canonical_url or job.title] = job
            except Exception as exc:
                errors.append(f"Adzuna query '{term}': {exc}")

        found = list(jobs.values())[: query.limit]
        return ProviderResult(
            provider_name=self.name,
            jobs=found,
            total_found=len(found),
            errors=errors,
        )

    def _normalize(self, raw: dict) -> Job:
        description = raw.get("description") or ""
        location = (raw.get("location") or {}).get("display_name")
        title = raw.get("title") or "Unknown"
        url = raw.get("redirect_url")
        required, preferred = _extract_skills_from_text(description)
        min_exp, max_exp = _extract_experience(description)
        posted_at = None
        with contextlib.suppress(ValueError, AttributeError):
            posted_at = datetime.fromisoformat(raw["created"].replace("Z", "+00:00"))

        contract_time = raw.get("contract_time")
        employment_type = (
            EmploymentType.FULL_TIME
            if contract_time == "full_time"
            else EmploymentType.PART_TIME
            if contract_time == "part_time"
            else EmploymentType.UNKNOWN
        )

        return Job(
            external_id=str(raw.get("id") or ""),
            company=(raw.get("company") or {}).get("display_name") or "Unknown",
            title=title,
            normalized_title=_normalize_title(title),
            location=location,
            country="India" if self.country == "in" else self.country.upper(),
            remote_type=_detect_remote(location or "", description),
            employment_type=employment_type,
            description=description,
            required_skills=required,
            preferred_skills=preferred,
            min_experience=min_exp,
            max_experience=max_exp,
            salary_min=raw.get("salary_min"),
            salary_max=raw.get("salary_max"),
            source=self.name,
            source_url=url,
            canonical_url=url,
            application_url=url,
            ats_provider=ATSProvider.GENERIC,
            posted_at=posted_at,
            discovered_at=datetime.now(UTC),
        )

    async def fetch_job(self, job_url: str) -> Job | None:
        return None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
