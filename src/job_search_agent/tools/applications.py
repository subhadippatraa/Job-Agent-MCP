"""MCP tools — application tracking and preparation."""

from __future__ import annotations

from datetime import datetime

from job_search_agent.config import get_settings
from job_search_agent.database import get_session, init_db
from job_search_agent.database.repository import (
    ApplicationRepository,
    JobRepository,
)
from job_search_agent.logging import get_logger
from job_search_agent.matching.scorer import score_job
from job_search_agent.models.application import Application, ApplicationPrep
from job_search_agent.models.candidate import CandidateProfile, load_candidate_profile
from job_search_agent.resume import get_relevant_bullets, get_resume

logger = get_logger(__name__)

# Sensitive fields that must never be auto-answered
SENSITIVE_FIELDS = [
    "salary_expectation",
    "work_authorization",
    "disability_status",
    "veteran_status",
    "gender",
    "race_ethnicity",
    "notice_period",
    "relocation_willingness",
    "background_check_consent",
    "security_clearance",
    "visa_sponsorship",
]


async def save_job(job_id: str) -> dict:
    """Save a discovered job to the database.

    Args:
        job_id: The internal job ID
    """
    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}

        await repo.update_status(job_id, "discovered")
        await session.commit()
        return {"status": "saved", "job_id": job_id}
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}
    finally:
        await session.close()


async def shortlist_job(job_id: str) -> dict:
    """Mark a job as shortlisted for application.

    Args:
        job_id: The internal job ID
    """
    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}

        await repo.update_status(job_id, "shortlisted")
        await session.commit()
        return {
            "status": "shortlisted",
            "job_id": job_id,
            "company": job.company,
            "title": job.title,
        }
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}
    finally:
        await session.close()


async def skip_job(job_id: str, reason: str | None = None) -> dict:
    """Skip a job with an optional reason.

    Args:
        job_id: The internal job ID
        reason: Why the job was skipped (e.g., "too senior", "wrong location",
                "salary", "not interested", "duplicate", "skill mismatch")
    """
    await init_db()
    session = await get_session()
    try:
        repo = JobRepository(session)
        job = await repo.get_by_id(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}

        await repo.update_status(job_id, "skipped", skip_reason=reason)
        await session.commit()
        return {"status": "skipped", "job_id": job_id, "reason": reason}
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}
    finally:
        await session.close()


async def prepare_application(job_id: str) -> dict:
    """Prepare an application package for a specific job.

    Returns everything the candidate needs to apply WITHOUT fabricating any
    qualifications. Includes: match summary, relevant resume bullets,
    skills to emphasize, gaps, suggested messages, likely screening questions,
    and fields that require user input.

    Does NOT submit anything automatically.

    Args:
        job_id: The internal job ID to prepare for
    """
    settings = get_settings()
    candidate = load_candidate_profile(settings.resolve_path(settings.candidate_profile_path))
    resume = get_resume()

    await init_db()
    session = await get_session()
    try:
        job_repo = JobRepository(session)
        job = await job_repo.get_by_id(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}

        # Score the job
        match = score_job(job, candidate, resume)

        # Get relevant resume bullets
        relevant_bullets = []
        if resume:
            relevant_bullets = get_relevant_bullets(
                resume,
                job.required_skills,
                job.preferred_skills,
                max_bullets=10,
            )

        # Build requires_user_input list
        requires_input = []
        for field in SENSITIVE_FIELDS:
            candidate_val = getattr(candidate, field, None)
            if candidate_val is None:
                requires_input.append(field)

        # Likely screening questions
        screening_questions = _predict_screening_questions(job, candidate)

        # Application checklist
        checklist = _build_checklist(job, candidate)

        # Skills to emphasize
        skills_to_emphasize = [s for s in match.matched_skills if s in candidate.primary_skills]
        if not skills_to_emphasize:
            skills_to_emphasize = match.matched_skills[:5]

        # Important JD requirements
        important_reqs = _extract_important_requirements(job)

        # Suggested recruiter message
        recruiter_msg = _build_recruiter_message(job, candidate, match)

        # Cover letter points
        cover_points = _build_cover_letter_points(job, candidate, match)

        prep = ApplicationPrep(
            job_id=job_id,
            company=job.company,
            title=job.title,
            match_score=match.score,
            recommendation=match.recommendation,
            matched_skills=match.matched_skills,
            missing_required_skills=match.missing_required_skills,
            missing_preferred_skills=match.missing_preferred_skills,
            relevant_resume_bullets=relevant_bullets,
            skills_to_emphasize=skills_to_emphasize,
            potential_gaps=match.concerns,
            important_requirements=important_reqs,
            suggested_recruiter_message=recruiter_msg,
            suggested_cover_letter_points=cover_points,
            likely_screening_questions=screening_questions,
            requires_user_input=requires_input,
            application_checklist=checklist,
            application_url=job.application_url,
        )

        # Update job status to "prepared"
        await job_repo.update_status(job_id, "prepared")
        await session.commit()

        return prep.model_dump(mode="json")

    except Exception as e:
        await session.rollback()
        logger.error("prepare_error", error=str(e))
        return {"error": str(e)}
    finally:
        await session.close()


async def record_application(
    job_id: str,
    resume_version: str | None = None,
    application_url: str | None = None,
    notes: str | None = None,
    source: str | None = None,
) -> dict:
    """Record that an application has been submitted for a job.

    Args:
        job_id: The internal job ID
        resume_version: Which version of the resume was used
        application_url: URL where the application was submitted
        notes: Any notes about the application
        source: How the application was submitted (e.g., "direct", "linkedin", "referral")
    """
    await init_db()
    session = await get_session()
    try:
        job_repo = JobRepository(session)
        app_repo = ApplicationRepository(session)

        job = await job_repo.get_by_id(job_id)
        if not job:
            return {"error": f"Job not found: {job_id}"}

        # Check if already applied
        existing = await app_repo.get_by_job_id(job_id)
        if existing:
            return {
                "error": "Application already recorded for this job",
                "application_id": existing.id,
                "applied_at": existing.applied_at.isoformat() if existing.applied_at else None,
            }

        app = Application(
            job_id=job_id,
            status="applied",
            applied_at=datetime.utcnow(),
            resume_version=resume_version,
            application_url=application_url or job.application_url,
            notes=notes,
            source=source,
        )

        saved = await app_repo.save(app)
        await job_repo.update_status(job_id, "applied")
        await session.commit()

        return {
            "status": "recorded",
            "application_id": saved.id,
            "job_id": job_id,
            "company": job.company,
            "title": job.title,
            "applied_at": saved.applied_at.isoformat() if saved.applied_at else None,
        }
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}
    finally:
        await session.close()


async def update_application_status(
    job_id: str,
    status: str,
    notes: str | None = None,
) -> dict:
    """Update the status of an application.

    Valid statuses: discovered, analyzed, shortlisted, prepared, applied,
    assessment, recruiter_screen, interview, rejected, offer, withdrawn, skipped

    Args:
        job_id: The internal job ID
        status: New status
        notes: Optional notes about the status change
    """
    valid_statuses = {
        "discovered",
        "analyzed",
        "shortlisted",
        "prepared",
        "applied",
        "assessment",
        "recruiter_screen",
        "interview",
        "rejected",
        "offer",
        "withdrawn",
        "skipped",
    }
    if status not in valid_statuses:
        return {"error": f"Invalid status: {status}. Valid: {sorted(valid_statuses)}"}

    await init_db()
    session = await get_session()
    try:
        app_repo = ApplicationRepository(session)
        job_repo = JobRepository(session)

        # Find application
        app = await app_repo.get_by_job_id(job_id)
        if not app:
            return {"error": f"No application found for job: {job_id}"}

        await app_repo.update_status(app.id, status, notes)
        await job_repo.update_status(job_id, status)
        await session.commit()

        return {
            "status": "updated",
            "application_id": app.id,
            "new_status": status,
            "notes": notes,
        }
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}
    finally:
        await session.close()


async def get_applications(
    status: str | None = None,
    company: str | None = None,
    days: int | None = None,
    min_score: float | None = None,
    limit: int = 50,
) -> dict:
    """Get applications with filters.

    Args:
        status: Filter by status (e.g., "applied", "interview", "rejected")
        company: Filter by company name
        days: Only applications from the last N days
        min_score: Minimum match score
        limit: Maximum results
    """
    await init_db()
    session = await get_session()
    try:
        repo = ApplicationRepository(session)

        since = None
        if days:
            from datetime import timedelta

            since = datetime.utcnow() - timedelta(days=days)

        apps = await repo.search(
            status=status,
            company=company,
            min_score=min_score,
            since=since,
            limit=limit,
        )

        return {"applications": apps, "total": len(apps)}
    finally:
        await session.close()


# --- Helper functions ---


def _predict_screening_questions(job, candidate: CandidateProfile) -> list[str]:
    """Predict likely screening questions based on job requirements."""
    questions = []

    if job.min_experience:
        questions.append(
            f"How many years of relevant experience do you have? (Job asks for {job.min_experience}+)"
        )

    if any(s.lower() in ["python", "java", "go"] for s in job.required_skills):
        lang = [
            s
            for s in job.required_skills
            if s.lower() in ["python", "java", "go", "rust", "typescript"]
        ]
        if lang:
            questions.append(f"Rate your proficiency in {', '.join(lang)}")

    if job.remote_type in ("onsite", "hybrid"):
        questions.append("Are you willing to work on-site/hybrid?")

    # Standard questions
    questions.extend(
        [
            "Are you authorized to work in this country?",
            "What is your expected salary range?",
            "What is your notice period / earliest start date?",
            "Are you willing to undergo a background check?",
        ]
    )

    return questions


def _build_checklist(job, candidate: CandidateProfile) -> list[str]:
    """Build an application checklist."""
    checklist = [
        "Review job description thoroughly",
        "Update resume to emphasize relevant skills",
    ]

    if job.required_skills:
        checklist.append("Verify you address key required skills in your application")

    checklist.extend(
        [
            "Prepare answers for likely screening questions",
            "Research the company",
            "Check application URL is accessible",
        ]
    )

    if candidate.links.get("linkedin"):
        checklist.append("Ensure LinkedIn profile is up to date")
    if candidate.links.get("github"):
        checklist.append("Ensure GitHub profile showcases relevant projects")

    checklist.append("Submit application and record it in the tracker")

    return checklist


def _extract_important_requirements(job) -> list[str]:
    """Extract the most important requirements from a job posting."""
    reqs = []

    if job.required_skills:
        reqs.append(f"Required skills: {', '.join(job.required_skills[:8])}")

    if job.min_experience:
        exp_str = f"{job.min_experience}+ years"
        if job.max_experience:
            exp_str = f"{job.min_experience}-{job.max_experience} years"
        reqs.append(f"Experience: {exp_str}")

    if job.location:
        reqs.append(f"Location: {job.location}")

    if job.employment_type and job.employment_type != "unknown":
        reqs.append(f"Type: {job.employment_type}")

    return reqs


def _build_recruiter_message(job, candidate: CandidateProfile, match) -> str:
    """Build a suggested recruiter message (candidate should customize)."""
    name = candidate.name
    skills = ", ".join(match.matched_skills[:4]) if match.matched_skills else "relevant skills"
    exp = f"{candidate.years_experience} years" if candidate.years_experience else "relevant"

    return (
        f"Hi,\n\n"
        f"I'm {name}, and I'm excited about the {job.title} role at {job.company}. "
        f"With {exp} of experience in {skills}, I believe I'd be a strong fit.\n\n"
        f"I'd love to discuss how my background aligns with what you're looking for.\n\n"
        f"Best regards,\n{name}"
    )


def _build_cover_letter_points(job, candidate: CandidateProfile, match) -> list[str]:
    """Build suggested cover letter talking points."""
    points = []

    if match.matched_skills:
        top_skills = match.matched_skills[:4]
        points.append(f"Highlight hands-on experience with {', '.join(top_skills)}")

    if match.strengths:
        for s in match.strengths[:2]:
            points.append(f"Emphasize: {s}")

    if job.company:
        points.append(f"Show genuine interest in {job.company}'s mission/product")

    if match.missing_required_skills:
        points.append(
            f"Address gap: acknowledge {', '.join(match.missing_required_skills[:2])} "
            f"and describe willingness/ability to learn"
        )

    return points
