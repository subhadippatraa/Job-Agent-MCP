"""MCP tools — LLM-enhanced analysis and comparison."""

from __future__ import annotations

from job_search_agent.config import get_settings
from job_search_agent.database import get_session, init_db
from job_search_agent.database.repository import JobRepository
from job_search_agent.llm import get_llm_provider
from job_search_agent.llm.analyzer import (
    llm_compare_jobs,
    llm_extract_requirements,
    llm_summarize_job,
    merge_llm_extraction,
)
from job_search_agent.logging import get_logger
from job_search_agent.matching.scorer import score_job
from job_search_agent.models.candidate import load_candidate_profile
from job_search_agent.providers.greenhouse import _extract_experience, _extract_skills_from_text
from job_search_agent.resume import get_resume

logger = get_logger(__name__)


async def enhance_job_analysis(job_id: str) -> dict:
    """Run LLM-enhanced analysis on a job's description.

    Augments the regex-extracted data with LLM-powered structured extraction.
    Adds seniority level, responsibilities, qualifications, tech stack,
    red flags, and skills that regex missed.

    Falls back to regex-only results if no LLM is configured.

    Args:
        job_id: The internal job ID
    """
    llm = get_llm_provider()

    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}

        if not job.description:
            return {"error": "Job has no description to analyze", "job_id": job_id}

        # Regex extraction (baseline)
        regex_required, regex_preferred = _extract_skills_from_text(job.description)
        regex_min_exp, regex_max_exp = _extract_experience(job.description)

        # LLM extraction (enhancement)
        llm_data = await llm_extract_requirements(llm, job.description)

        # Merge
        required, preferred, min_exp, max_exp, metadata = merge_llm_extraction(
            regex_skills=(regex_required, regex_preferred),
            regex_experience=(regex_min_exp, regex_max_exp),
            llm_data=llm_data,
        )

        # Summary
        summary = await llm_summarize_job(llm, job.description)

        # Update job in database with enhanced data
        if llm_data:
            if len(required) > len(job.required_skills):
                job.required_skills = required
            if len(preferred) > len(job.preferred_skills):
                job.preferred_skills = preferred
            if min_exp is not None and job.min_experience is None:
                job.min_experience = min_exp
            if max_exp is not None and job.max_experience is None:
                job.max_experience = max_exp

            await repo.update_job(job)
            await session.commit()

        result = {
            "job_id": job_id,
            "company": job.company,
            "title": job.title,
            "enhanced": llm_data is not None,
            "required_skills": required,
            "preferred_skills": preferred,
            "min_experience": min_exp,
            "max_experience": max_exp,
            "summary": summary,
        }

        if metadata:
            result["llm_metadata"] = metadata

        return result

    except Exception as e:
        await session.rollback()
        logger.error("enhance_error", error=str(e))
        return {"error": str(e)}
    finally:
        await llm.close()
        await session.close()


async def compare_jobs(
    job_id_a: str,
    job_id_b: str,
) -> dict:
    """Semantically compare two jobs side-by-side for the candidate.

    Uses both deterministic scoring AND LLM-powered semantic analysis.
    The deterministic scores are always available; LLM comparison is optional.

    Returns match scores for both, a recommendation, and detailed reasoning.

    Args:
        job_id_a: First job ID
        job_id_b: Second job ID
    """
    settings = get_settings()
    candidate = load_candidate_profile(settings.resolve_path(settings.candidate_profile_path))
    resume = get_resume()
    llm = get_llm_provider()

    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)

        job_a = await repo.get_by_id(job_id_a)
        job_b = await repo.get_by_id(job_id_b)

        if not job_a:
            return {"error": f"Job A not found: {job_id_a}"}
        if not job_b:
            return {"error": f"Job B not found: {job_id_b}"}

        # Deterministic scores
        match_a = score_job(job_a, candidate, resume)
        match_b = score_job(job_b, candidate, resume)

        # LLM semantic comparison
        llm_comparison = await llm_compare_jobs(
            llm=llm,
            job_a=job_a.model_dump(mode="json"),
            job_b=job_b.model_dump(mode="json"),
            candidate_skills=candidate.all_skills,
            candidate_roles=candidate.target_roles,
            candidate_experience=candidate.years_experience,
        )

        # Build the result
        result = {
            "job_a": {
                "id": job_id_a,
                "company": job_a.company,
                "title": job_a.title,
                "location": job_a.location,
                "score": match_a.score,
                "recommendation": match_a.recommendation,
                "matched_skills": match_a.matched_skills[:8],
                "missing_required": match_a.missing_required_skills[:5],
                "strengths": match_a.strengths,
                "concerns": match_a.concerns,
            },
            "job_b": {
                "id": job_id_b,
                "company": job_b.company,
                "title": job_b.title,
                "location": job_b.location,
                "score": match_b.score,
                "recommendation": match_b.recommendation,
                "matched_skills": match_b.matched_skills[:8],
                "missing_required": match_b.missing_required_skills[:5],
                "strengths": match_b.strengths,
                "concerns": match_b.concerns,
            },
            "deterministic_winner": "A"
            if match_a.score > match_b.score
            else ("B" if match_b.score > match_a.score else "tie"),
            "score_difference": abs(match_a.score - match_b.score),
        }

        # Add LLM analysis if available
        if llm_comparison:
            result["llm_analysis"] = llm_comparison
            result["has_llm_analysis"] = True
        else:
            result["has_llm_analysis"] = False

        return result

    except Exception as e:
        logger.error("compare_error", error=str(e))
        return {"error": str(e)}
    finally:
        await llm.close()
        await session.close()
