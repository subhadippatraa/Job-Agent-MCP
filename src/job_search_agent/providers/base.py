"""Abstract base class for job discovery providers."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from job_search_agent.models.job import Job, RemoteType


@dataclass
class SearchQuery:
    """Normalized search query passed to providers."""

    keywords: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    location: str | None = None
    country: str | None = None
    remote_only: bool = False
    experience_min: int | None = None
    experience_max: int | None = None
    posted_within_hours: int | None = None
    skills: list[str] = field(default_factory=list)
    limit: int = 50


@dataclass
class ProviderResult:
    """Result from a single provider search."""

    provider_name: str
    jobs: list[Job] = field(default_factory=list)
    total_found: int = 0
    errors: list[str] = field(default_factory=list)
    rate_limited: bool = False


def matches_query(job: Job, query: SearchQuery) -> bool:
    """Apply the shared search filters to a normalized job."""
    text = f"{job.title or ''}\n{job.description or ''}".lower()
    terms = [*query.roles, *query.keywords]
    if terms and not any(term.lower() in text for term in terms):
        return False

    if query.remote_only and job.remote_type not in ("remote", RemoteType.REMOTE):
        return False

    location = f"{job.location or ''} {job.country or ''}".lower()
    if (
        query.location
        and query.location.lower() not in location
        and job.remote_type
        not in (
            "remote",
            RemoteType.REMOTE,
        )
    ):
        return False
    if query.country and query.country.lower() not in location:
        return False

    if query.experience_min is not None and (
        job.min_experience is None or job.min_experience < query.experience_min
    ):
        return False
    if (
        query.experience_max is not None
        and job.min_experience is not None
        and job.min_experience > query.experience_max + 1
    ):
        return False

    if query.posted_within_hours is not None:
        if job.posted_at is None:
            return False
        posted_at = (
            job.posted_at.replace(tzinfo=UTC) if job.posted_at.tzinfo is None else job.posted_at
        )
        if posted_at < datetime.now(UTC) - timedelta(hours=query.posted_within_hours):
            return False

    skills = {skill.lower() for skill in [*job.required_skills, *job.preferred_skills]}
    return not query.skills or all(skill.lower() in skills for skill in query.skills)


class JobProvider(abc.ABC):
    """Abstract base for job discovery providers.

    Each provider adapts a specific ATS or job source into the canonical Job schema.
    Providers must handle their own errors — a single provider failure must not
    crash the entire search.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique provider identifier (e.g., 'greenhouse', 'lever')."""
        ...

    @abc.abstractmethod
    async def search(self, query: SearchQuery) -> ProviderResult:
        """Search for jobs matching the query.

        Returns a ProviderResult with normalized Job objects.
        Must handle errors gracefully and report them in ProviderResult.errors.
        """
        ...

    @abc.abstractmethod
    async def fetch_job(self, job_url: str) -> Job | None:
        """Fetch and normalize a single job posting by URL.

        Returns None if the job cannot be fetched or parsed.
        """
        ...

    async def close(self) -> None:  # noqa: B027
        """Clean up resources (e.g., HTTP client). Override if needed."""
