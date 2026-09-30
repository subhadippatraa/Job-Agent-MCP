"""Provider registry and multi-provider search aggregation."""

from __future__ import annotations

from job_search_agent.providers.ashby import AshbyProvider
from job_search_agent.providers.base import JobProvider, ProviderResult, SearchQuery
from job_search_agent.providers.generic import GenericProvider
from job_search_agent.providers.greenhouse import GreenhouseProvider
from job_search_agent.providers.lever import LeverProvider

__all__ = [
    "AshbyProvider",
    "GenericProvider",
    "GreenhouseProvider",
    "JobProvider",
    "LeverProvider",
    "ProviderResult",
    "SearchQuery",
    "get_all_providers",
]


def get_all_providers() -> list[JobProvider]:
    """Get all configured job providers."""
    return [
        GreenhouseProvider(),
        LeverProvider(),
        AshbyProvider(),
    ]
