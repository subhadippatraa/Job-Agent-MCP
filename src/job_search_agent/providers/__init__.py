"""Provider registry and multi-provider search aggregation."""

from __future__ import annotations

from job_search_agent.config import get_settings
from job_search_agent.providers.adzuna import AdzunaProvider
from job_search_agent.providers.ashby import AshbyProvider
from job_search_agent.providers.base import JobProvider, ProviderResult, SearchQuery
from job_search_agent.providers.generic import GenericProvider
from job_search_agent.providers.greenhouse import GreenhouseProvider
from job_search_agent.providers.lever import LeverProvider
from job_search_agent.providers.remoteok import RemoteOKProvider

__all__ = [
    "AshbyProvider",
    "AdzunaProvider",
    "GenericProvider",
    "GreenhouseProvider",
    "JobProvider",
    "LeverProvider",
    "RemoteOKProvider",
    "ProviderResult",
    "SearchQuery",
    "get_all_providers",
]


def get_all_providers() -> list[JobProvider]:
    """Get all configured job providers."""
    providers: list[JobProvider] = [
        GreenhouseProvider(),
        LeverProvider(),
        AshbyProvider(),
        RemoteOKProvider(),
    ]
    settings = get_settings()
    if settings.adzuna_app_id and settings.adzuna_app_key:
        providers.append(AdzunaProvider())
    return providers
