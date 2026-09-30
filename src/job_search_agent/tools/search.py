"""MCP tools — job search and discovery."""

from __future__ import annotations

import asyncio

from job_search_agent.config import get_settings
from job_search_agent.database import get_session, init_db
from job_search_agent.database.repository import JobRepository, SearchRunRepository
from job_search_agent.logging import get_logger
from job_search_agent.matching.scorer import score_job
from job_search_agent.models.candidate import load_candidate_profile
from job_search_agent.models.job import Job
from job_search_agent.providers import (
    ProviderResult,
    SearchQuery,
    get_all_providers,
)
from job_search_agent.resume import get_resume

logger = get_logger(__name__)


async def search_jobs(
    keywords: list[str] | None = None,
    roles: list[str] | None = None,
    location: str | None = None,
    remote_only: bool = False,
    country: str | None = None,
    experience_min: int | None = None,
    experience_max: int | None = None,
    posted_within_hours: int | None = None,
    skills: list[str] | None = None,
    limit: int = 50,
    sources: list[str] | None = None,
) -> dict:
    """Search for jobs across all configured providers.

    Returns normalized, deduplicated job objects from Greenhouse, Lever, Ashby,
    and other configured sources.

    Args:
        keywords: Search keywords (e.g., ["RAG", "LLM"])
        roles: Target role names (e.g., ["AI Engineer", "LLM Engineer"])
        location: Preferred location (e.g., "Bangalore", "Remote")
        remote_only: Only return remote positions
        country: Country filter (e.g., "India", "US")
        experience_min: Minimum years of experience
        experience_max: Maximum years of experience the candidate has
        posted_within_hours: Only jobs posted within this many hours
        skills: Required skills to match
        limit: Maximum number of results
        sources: Specific providers to search (e.g., ["greenhouse", "lever"])
    """
    settings = get_settings()

    query = SearchQuery(
        keywords=keywords or [],
        roles=roles or [],
        location=location,
        country=country,
        remote_only=remote_only,
        experience_min=experience_min,
        experience_max=experience_max,
        posted_within_hours=posted_within_hours or settings.default_posted_within_hours,
        skills=skills or [],
        limit=limit,
    )

    # Get providers
    providers = get_all_providers()
    if sources:
        source_set = set(s.lower() for s in sources)
        providers = [p for p in providers if p.name in source_set]

    # Search all providers concurrently (errors isolated per provider)
    results: list[ProviderResult] = []
    tasks = [p.search(query) for p in providers]
    provider_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_jobs: list[Job] = []
    all_errors: list[str] = []
    providers_used: list[str] = []

    for i, result in enumerate(provider_results):
        if isinstance(result, Exception):
            all_errors.append(f"{providers[i].name}: {result}")
        elif isinstance(result, ProviderResult):
            results.append(result)
            all_jobs.extend(result.jobs)
            all_errors.extend(result.errors)
            providers_used.append(result.provider_name)

    # Deduplicate
    deduped_jobs, duplicates_skipped = _deduplicate(all_jobs)

    # Save to database
    await init_db()
    session = await get_session()
    try:
        job_repo = JobRepository(session)
        search_repo = SearchRunRepository(session)

        saved_jobs: list[Job] = []
        new_count = 0

        for job in deduped_jobs[:limit]:
            # Check if already exists
            existing = None
            if job.canonical_url:
                existing = await job_repo.get_by_canonical_url(job.canonical_url)
            if not existing:
                existing = await job_repo.find_duplicate(job.company, job.title, job.location)

            if existing:
                duplicates_skipped += 1
                saved_jobs.append(existing)
            else:
                saved = await job_repo.save(job)
                saved_jobs.append(saved)
                new_count += 1

        # Log search run
        await search_repo.log_search(
            query_params={
                "keywords": query.keywords,
                "roles": query.roles,
                "location": query.location,
                "remote_only": query.remote_only,
                "limit": query.limit,
            },
            providers=providers_used,
            total_results=len(all_jobs),
            new_jobs=new_count,
            duplicates_skipped=duplicates_skipped,
            errors=[{"message": e} for e in all_errors] if all_errors else None,
        )

        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error("search_save_error", error=str(e))
        raise
    finally:
        await session.close()

    # Close providers
    for p in providers:
        await p.close()

    return {
        "jobs": [j.model_dump(mode="json", exclude_none=True) for j in saved_jobs[:limit]],
        "total_found": len(all_jobs),
        "new_jobs": new_count,
        "duplicates_skipped": duplicates_skipped,
        "providers_used": providers_used,
        "errors": all_errors if all_errors else None,
    }


async def search_jobs_for_candidate() -> dict:
    """High-level agent tool: search using the candidate's profile, score, and rank results.

    Reads the candidate profile and resume automatically, searches for jobs matching
    target roles, scores all results, removes duplicates, and returns ranked opportunities.

    This is the primary tool for queries like: "Find the best new jobs for me."
    """
    settings = get_settings()

    # Load candidate
    profile_path = settings.resolve_path(settings.candidate_profile_path)
    candidate = load_candidate_profile(profile_path)

    # Load resume
    resume = get_resume()

    # Search using candidate target roles
    search_result = await search_jobs(
        roles=candidate.target_roles,
        location=candidate.preferred_locations[0] if candidate.preferred_locations else None,
        experience_max=int(candidate.years_experience or 3) + 1,
        limit=settings.default_search_limit,
    )

    # Score each job
    scored_jobs = []
    for job_data in search_result.get("jobs", []):
        job = Job(**job_data)
        match = score_job(job, candidate, resume)

        job_data["match_score"] = match.score
        job_data["recommendation"] = match.recommendation
        job_data["matched_skills"] = match.matched_skills
        job_data["missing_required_skills"] = match.missing_required_skills
        job_data["strengths"] = match.strengths
        job_data["concerns"] = match.concerns

        scored_jobs.append(job_data)

        # Update score in DB
        if job.id:
            await init_db()
            session = await get_session()
            try:
                job_repo = JobRepository(session)
                await job_repo.update_match_score(job.id, match.score)
                await session.commit()
            except Exception:
                await session.rollback()
            finally:
                await session.close()

    # Sort by score descending
    scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)

    return {
        "candidate": candidate.name,
        "target_roles": candidate.target_roles,
        "jobs": scored_jobs,
        "total": len(scored_jobs),
        "providers_used": search_result.get("providers_used", []),
        "errors": search_result.get("errors"),
    }


def _deduplicate(jobs: list[Job]) -> tuple[list[Job], int]:
    """Deduplicate jobs by canonical URL and company+title."""
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    unique: list[Job] = []
    dups = 0

    for job in jobs:
        # URL-based dedup
        if job.canonical_url:
            if job.canonical_url in seen_urls:
                dups += 1
                continue
            seen_urls.add(job.canonical_url)

        # Company+title dedup
        key = f"{job.company.lower()}:{(job.normalized_title or job.title).lower()}"
        if key in seen_keys:
            dups += 1
            continue
        seen_keys.add(key)

        unique.append(job)

    return unique, dups
