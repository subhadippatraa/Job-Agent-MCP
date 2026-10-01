"""MCP tools — job analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from job_search_agent.database import get_session, init_db
from job_search_agent.database.repository import JobRepository
from job_search_agent.logging import get_logger
from job_search_agent.models.job import JobStatus
from job_search_agent.providers.generic import GenericProvider
from job_search_agent.providers.greenhouse import GreenhouseProvider
from job_search_agent.providers.lever import LeverProvider

if TYPE_CHECKING:
    from job_search_agent.providers.base import JobProvider

logger = get_logger(__name__)


async def get_job(job_id: str) -> dict:
    """Get complete normalized information for a specific job.

    Args:
        job_id: The internal job ID (UUID)
    """
    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}
        return job.model_dump(mode="json", exclude_none=True)
    finally:
        await session.close()


async def analyze_job_url(url: str) -> dict:
    """Fetch and analyze a job posting from any URL.

    Extracts: company, title, location, employment type, remote status,
    salary (if listed), required/preferred experience, skills,
    responsibilities, qualifications, ATS provider, and posting date.

    Unknown values remain null — the system never guesses missing information.

    Args:
        url: The job posting URL to analyze
    """
    job = None
    provider: JobProvider

    # Try specialized providers first based on URL
    if "greenhouse.io" in url:
        provider = GreenhouseProvider()
        job = await provider.fetch_job(url)
        await provider.close()
    elif "lever.co" in url:
        provider = LeverProvider()
        job = await provider.fetch_job(url)
        await provider.close()

    # Fall back to generic
    if job is None:
        generic = GenericProvider()
        job = await generic.fetch_job(url)
        await generic.close()

    if job is None:
        return {"error": f"Could not fetch or parse job at: {url}"}

    # Save to database
    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)

        # Check for duplicates
        existing = await repo.get_by_canonical_url(url)
        if existing:
            return {
                "job": existing.model_dump(mode="json", exclude_none=True),
                "note": "Job already exists in database",
            }

        job.status = JobStatus.ANALYZED
        saved = await repo.save(job)
        await session.commit()
        return {"job": saved.model_dump(mode="json", exclude_none=True)}
    except Exception as e:
        await session.rollback()
        logger.error("analyze_save_error", error=str(e))
        return {"job": job.model_dump(mode="json", exclude_none=True), "save_error": str(e)}
    finally:
        await session.close()


async def check_duplicate_job(
    url: str | None = None,
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
) -> dict:
    """Check if a job posting is a duplicate of one already in the database.

    Detects duplicates using: canonical URL, company + normalized title + location.

    Args:
        url: Job posting URL
        company: Company name
        title: Job title
        location: Job location
    """
    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)

        # URL-based check
        if url:
            existing = await repo.get_by_canonical_url(url)
            if existing:
                return {
                    "is_duplicate": True,
                    "existing_job_id": existing.id,
                    "match_method": "canonical_url",
                    "existing_job": {
                        "company": existing.company,
                        "title": existing.title,
                        "status": existing.status,
                    },
                }

        # Company+title check
        if company and title:
            existing = await repo.find_duplicate(company, title, location)
            if existing:
                return {
                    "is_duplicate": True,
                    "existing_job_id": existing.id,
                    "match_method": "company_title",
                    "existing_job": {
                        "company": existing.company,
                        "title": existing.title,
                        "status": existing.status,
                    },
                }

        return {"is_duplicate": False}
    finally:
        await session.close()
