"""MCP tools — statistics and daily digest."""

from __future__ import annotations

from datetime import datetime, timedelta

from job_search_agent.database import get_session, init_db
from job_search_agent.database.repository import ApplicationRepository, JobRepository
from job_search_agent.logging import get_logger

logger = get_logger(__name__)


async def get_job_stats() -> dict:
    """Get comprehensive job search statistics.

    Returns: jobs discovered, shortlisted, applications submitted,
    interviews, rejections, offers, average match score, and more.
    """
    await init_db()
    session = await get_session()
    try:
        job_repo = JobRepository(session)
        app_repo = ApplicationRepository(session)

        job_stats = await job_repo.get_stats()
        app_stats = await app_repo.get_stats()

        return {
            "jobs": job_stats,
            "applications": app_stats,
            "summary": {
                "total_jobs_discovered": job_stats.get("total_jobs", 0),
                "jobs_shortlisted": job_stats.get("by_status", {}).get("shortlisted", 0),
                "applications_submitted": app_stats.get("by_status", {}).get("applied", 0),
                "interviews": app_stats.get("by_status", {}).get("interview", 0),
                "rejections": app_stats.get("by_status", {}).get("rejected", 0),
                "offers": app_stats.get("by_status", {}).get("offer", 0),
                "average_match_score": job_stats.get("average_match_score"),
            },
        }
    finally:
        await session.close()


async def get_daily_job_digest(
    hours: int = 24,
    min_score: float | None = None,
    limit: int = 10,
) -> dict:
    """Get the best new job opportunities since a specified time.

    Example: "Give me today's top 10 new opportunities."

    Args:
        hours: Look back this many hours (default: 24)
        min_score: Minimum match score to include
        limit: Maximum number of jobs to return
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)
        jobs = await repo.get_recent(
            since=since,
            min_score=min_score,
            limit=limit,
        )

        return {
            "digest_period": f"Last {hours} hours",
            "since": since.isoformat(),
            "total": len(jobs),
            "min_score_filter": min_score,
            "jobs": [
                {
                    "id": j.id,
                    "company": j.company,
                    "title": j.title,
                    "location": j.location,
                    "remote_type": j.remote_type,
                    "match_score": j.match_score,
                    "status": j.status,
                    "source": j.source,
                    "discovered_at": j.discovered_at.isoformat() if j.discovered_at else None,
                    "application_url": j.application_url,
                }
                for j in jobs
            ],
        }
    finally:
        await session.close()
