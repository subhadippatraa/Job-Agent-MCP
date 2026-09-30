"""Abstract base class for job discovery providers."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_search_agent.models.job import Job


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
