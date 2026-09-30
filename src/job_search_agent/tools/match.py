"""MCP tools — job matching and ranking."""

from __future__ import annotations

from job_search_agent.config import get_settings
from job_search_agent.database import get_session, init_db
from job_search_agent.database.repository import JobRepository, MatchRepository
from job_search_agent.logging import get_logger
from job_search_agent.matching.scorer import score_job
from job_search_agent.models.candidate import load_candidate_profile
from job_search_agent.models.job import Job
from job_search_agent.resume import get_resume

logger = get_logger(__name__)


async def match_job_to_candidate(
    job_id: str | None = None,
    job_description: str | None = None,
) -> dict:
    """Compare a job against the candidate profile and resume.

    Returns an explainable, deterministic match score with detailed breakdown.
    Every point in the score is accounted for.

    Args:
        job_id: Internal job ID to match (looks up from database)
        job_description: Raw job description text to match (alternative to job_id)
    """
    settings = get_settings()

    # Load candidate
    candidate = load_candidate_profile(settings.resolve_path(settings.candidate_profile_path))
    resume = get_resume()

    # Get job
    job = None
    if job_id:
        await init_db()
        session = await get_session()
        try:
            repo = JobRepository(session)
            job = await repo.get_by_id(job_id)
        finally:
            await session.close()

        if not job:
            return {"error": f"Job not found: {job_id}"}

    elif job_description:
        # Create a temporary Job from raw description
        job = Job(
            company="Unknown",
            title="Unknown",
            description=job_description,
        )
        # Extract skills from description
        from job_search_agent.providers.greenhouse import (
            _extract_experience,
            _extract_skills_from_text,
        )
        req, pref = _extract_skills_from_text(job_description)
        job.required_skills = req
        job.preferred_skills = pref
        min_exp, max_exp = _extract_experience(job_description)
        job.min_experience = min_exp
        job.max_experience = max_exp
    else:
        return {"error": "Provide either job_id or job_description"}

    # Score
    match = score_job(job, candidate, resume)

    # Cache match result in database
    if job_id and job.id:
        await init_db()
        session = await get_session()
        try:
            match_repo = MatchRepository(session)
            await match_repo.save(job_id, match)
            # Update job score
            job_repo = JobRepository(session)
            await job_repo.update_match_score(job_id, match.score)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("match_save_error", error=str(e))
        finally:
            await session.close()

    result = match.model_dump(mode="json", exclude={"skill_details"})

    # Add job context
    if job_id:
        result["job"] = {
            "id": job.id,
            "company": job.company,
            "title": job.title,
            "location": job.location,
        }

    return result


async def rank_jobs(
    job_ids: list[str],
    min_score: float | None = None,
) -> dict:
    """Rank a set of jobs by candidate match score.

    Args:
        job_ids: List of internal job IDs to rank
        min_score: Optional minimum score threshold (0-100)
    """
    settings = get_settings()
    candidate = load_candidate_profile(settings.resolve_path(settings.candidate_profile_path))
    resume = get_resume()

    await init_db()
    session = await get_session()
    try:
        job_repo = JobRepository(session)
        match_repo = MatchRepository(session)

        ranked: list[dict] = []

        for job_id in job_ids:
            job = await job_repo.get_by_id(job_id)
            if not job:
                continue

            # Check cache first
            cached = await match_repo.get_by_job_id(job_id)
            if cached:
                match = cached
            else:
                match = score_job(job, candidate, resume)
                await match_repo.save(job_id, match)
                await job_repo.update_match_score(job_id, match.score)

            if min_score is not None and match.score < min_score:
                continue

            ranked.append({
                "job_id": job_id,
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "score": match.score,
                "recommendation": match.recommendation,
                "matched_skills": match.matched_skills[:5],
                "missing_required_skills": match.missing_required_skills[:3],
                "strengths": match.strengths[:2],
                "concerns": match.concerns[:2],
            })

        await session.commit()
    finally:
        await session.close()

    # Sort by score
    ranked.sort(key=lambda x: x["score"], reverse=True)

    return {
        "ranked_jobs": ranked,
        "total": len(ranked),
        "min_score_filter": min_score,
    }
