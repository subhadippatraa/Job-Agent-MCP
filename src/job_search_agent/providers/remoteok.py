"""Remote OK public-feed provider."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

import httpx

from job_search_agent.config import get_settings
from job_search_agent.models.job import ATSProvider, Job, RemoteType
from job_search_agent.providers.base import JobProvider, ProviderResult, SearchQuery, matches_query
from job_search_agent.providers.greenhouse import (
    _extract_experience,
    _extract_skills_from_text,
    _normalize_title,
    _strip_html,
)

API = "https://remoteok.com/api"
INDIA_ELIGIBLE = ("worldwide", "anywhere", "global", "india", "asia", "apac")


def _open_to_india(raw: dict) -> bool:
    text = " ".join([str(raw.get("location") or ""), *(raw.get("tags") or [])]).lower()
    return any(term in text for term in INDIA_ELIGIBLE)


class RemoteOKProvider(JobProvider):
    """Find global-remote jobs whose listing explicitly includes India."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "remoteok"

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=get_settings().http_timeout_seconds,
                headers={"Accept": "application/json", "User-Agent": "JobSearchAgent/0.1"},
                follow_redirects=True,
            )
        return self._client

    async def search(self, query: SearchQuery) -> ProviderResult:
        try:
            response = await self.client.get(API)
            response.raise_for_status()
            jobs = []
            for raw in response.json():
                if not isinstance(raw, dict) or not raw.get("id") or not _open_to_india(raw):
                    continue
                job = self._normalize(raw)
                if matches_query(job, query):
                    jobs.append(job)
                if len(jobs) == query.limit:
                    break
            return ProviderResult(
                provider_name=self.name,
                jobs=jobs,
                total_found=len(jobs),
            )
        except Exception as exc:
            return ProviderResult(provider_name=self.name, errors=[f"Remote OK: {exc}"])

    def _normalize(self, raw: dict) -> Job:
        description = _strip_html(raw.get("description") or "")
        title = raw.get("position") or "Unknown"
        required, preferred = _extract_skills_from_text(description)
        min_exp, max_exp = _extract_experience(description)
        posted_at = None
        with contextlib.suppress(ValueError, AttributeError):
            posted_at = datetime.fromisoformat(raw["date"].replace("Z", "+00:00"))
        url = raw.get("apply_url") or raw.get("url")

        return Job(
            external_id=str(raw["id"]),
            company=raw.get("company") or "Unknown",
            title=title,
            normalized_title=_normalize_title(title),
            location=raw.get("location") or "Worldwide",
            remote_type=RemoteType.REMOTE,
            description=description,
            required_skills=required,
            preferred_skills=preferred,
            min_experience=min_exp,
            max_experience=max_exp,
            salary_min=raw.get("salary_min") or None,
            salary_max=raw.get("salary_max") or None,
            source=self.name,
            source_url=raw.get("url") or url,
            canonical_url=raw.get("url") or url,
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
