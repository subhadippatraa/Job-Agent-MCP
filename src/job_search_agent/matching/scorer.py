"""Composite matching scorer — deterministic, explainable, configurable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from job_search_agent.config import MatchWeights, get_settings
from job_search_agent.matching.experience import compute_experience_score
from job_search_agent.matching.skills import compute_skill_score, match_skills
from job_search_agent.matching.titles import compute_title_similarity
from job_search_agent.models.job import Job, RemoteType
from job_search_agent.models.match import MatchResult, ScoreBreakdown

if TYPE_CHECKING:
    from job_search_agent.models.candidate import CandidateProfile
    from job_search_agent.resume.parser import ResumeData


def score_job(
    job: Job,
    candidate: CandidateProfile,
    resume: ResumeData | None = None,
    weights: MatchWeights | None = None,
) -> MatchResult:
    """Score a job against the candidate profile.

    Every point in the final score is accounted for in the breakdown.
    The algorithm is fully deterministic — no LLM calls.

    Weight categories (configurable):
        Required skills:  35%
        Experience:        20%
        Role similarity:   15%
        Preferred skills:  10%
        Location/remote:   10%
        Domain relevance:  10%
    """
    if weights is None:
        weights = get_settings().match_weights

    # --- 1. Skills matching ---
    resume_evidence = None
    if resume:
        all_job_skills = job.required_skills + job.preferred_skills
        resume_evidence = resume.build_evidence_map(all_job_skills)

    required_matches, preferred_matches = match_skills(
        candidate_skills=candidate.all_skills,
        job_required=job.required_skills,
        job_preferred=job.preferred_skills,
        resume_evidence=resume_evidence,
    )

    required_skills_score = compute_skill_score(required_matches)
    preferred_skills_score = compute_skill_score(preferred_matches)

    matched = [m.skill for m in required_matches + preferred_matches if m.matched]
    missing_required = [m.skill for m in required_matches if not m.matched]
    missing_preferred = [m.skill for m in preferred_matches if not m.matched]

    req_matched_count = sum(1 for m in required_matches if m.matched)
    req_detail = (
        f"{req_matched_count}/{len(required_matches)} required skills matched"
        if required_matches
        else "No required skills listed"
    )

    pref_matched_count = sum(1 for m in preferred_matches if m.matched)
    pref_detail = (
        f"{pref_matched_count}/{len(preferred_matches)} preferred skills matched"
        if preferred_matches
        else "No preferred skills listed"
    )

    # --- 2. Experience matching ---
    exp_score, exp_detail = compute_experience_score(
        candidate_years=candidate.years_experience,
        job_min_years=job.min_experience,
        job_max_years=job.max_experience,
    )

    experience_match = exp_score >= 60.0
    experience_gap = exp_detail if exp_score < 85 else None

    # --- 3. Role/title similarity ---
    role_score, role_detail = compute_title_similarity(
        candidate_target_roles=candidate.target_roles,
        job_title=job.title,
    )

    # --- 4. Location/remote match ---
    location_score, location_detail = _score_location(job, candidate)
    location_match = location_score >= 50.0

    # --- 5. Domain relevance ---
    domain_score, domain_detail = _score_domain(job, candidate)

    # --- Composite score ---
    composite = (
        required_skills_score * weights.required_skills
        + preferred_skills_score * weights.preferred_skills
        + exp_score * weights.experience
        + role_score * weights.role_similarity
        + location_score * weights.location
        + domain_score * weights.domain
    )

    # Clamp to 0-100
    composite = max(0.0, min(100.0, round(composite, 1)))

    # --- Build result ---
    breakdown = ScoreBreakdown(
        required_skills_score=round(required_skills_score, 1),
        required_skills_weight=weights.required_skills,
        required_skills_detail=req_detail,
        preferred_skills_score=round(preferred_skills_score, 1),
        preferred_skills_weight=weights.preferred_skills,
        preferred_skills_detail=pref_detail,
        experience_score=round(exp_score, 1),
        experience_weight=weights.experience,
        experience_detail=exp_detail,
        role_similarity_score=round(role_score, 1),
        role_similarity_weight=weights.role_similarity,
        role_similarity_detail=role_detail,
        location_score=round(location_score, 1),
        location_weight=weights.location,
        location_detail=location_detail,
        domain_score=round(domain_score, 1),
        domain_weight=weights.domain,
        domain_detail=domain_detail,
    )

    # Strengths and concerns
    strengths = _build_strengths(
        required_skills_score,
        exp_score,
        role_score,
        location_score,
        req_matched_count,
        len(required_matches),
    )
    concerns = _build_concerns(
        missing_required,
        missing_preferred,
        exp_score,
        experience_gap,
        location_score,
        role_score,
    )

    # Resume evidence for matched skills
    resume_evidence_list = []
    if resume:
        for m in required_matches + preferred_matches:
            if m.matched and m.candidate_evidence:
                resume_evidence_list.append(f"[{m.skill}] {m.candidate_evidence}")

    recommendation = MatchResult.classify_score(composite)

    return MatchResult(
        job_id=job.id,
        score=composite,
        recommendation=recommendation,
        experience_match=experience_match,
        location_match=location_match,
        matched_skills=matched,
        missing_required_skills=missing_required,
        missing_preferred_skills=missing_preferred,
        skill_details=required_matches + preferred_matches,
        experience_gap=experience_gap,
        strengths=strengths,
        concerns=concerns,
        resume_evidence=resume_evidence_list,
        breakdown=breakdown,
    )


def _score_location(job: Job, candidate: CandidateProfile) -> tuple[float, str]:
    """Score location match."""
    # If candidate wants remote and job is remote → perfect match
    if candidate.remote_preference == "remote_only":
        if job.remote_type in (RemoteType.REMOTE, "remote"):
            return 100.0, "Remote job matches remote preference"
        return 30.0, f"Candidate prefers remote; job is {job.remote_type}"

    # If job is remote, most candidates are happy
    if job.remote_type in (RemoteType.REMOTE, "remote"):
        return 100.0, "Remote job available"

    # Check location overlap
    if job.location and candidate.preferred_locations:
        job_loc_lower = job.location.lower()
        for pref in candidate.preferred_locations:
            if pref.lower() in job_loc_lower:
                return 100.0, f"Location match: job in {job.location}, candidate prefers {pref}"

    # Check country
    if job.country and candidate.preferred_countries:
        for country in candidate.preferred_countries:
            if country.lower() == (job.country or "").lower():
                return 80.0, f"Country match: {job.country}"

    # Flexible candidate
    if candidate.remote_preference == "flexible":
        return 60.0, "Candidate is flexible on location"

    # No location info
    if not job.location:
        return 70.0, "Job location not specified"

    return 40.0, f"Location mismatch: job in {job.location}"


def _score_domain(job: Job, candidate: CandidateProfile) -> tuple[float, str]:
    """Score domain/industry relevance."""
    if not candidate.domain_interests:
        return 70.0, "No domain preferences specified"

    description = (job.description or "").lower()
    title = (job.title or "").lower()
    combined = f"{title} {description}"

    # AI/ML domain keywords
    domain_keywords = {
        "ai/ml": [
            "artificial intelligence",
            "machine learning",
            "ai ",
            "ml ",
            "deep learning",
            "neural",
        ],
        "generative ai": [
            "generative ai",
            "genai",
            "gen ai",
            "llm",
            "language model",
            "gpt",
            "claude",
        ],
        "backend engineering": ["backend", "back-end", "api", "server", "microservice"],
        "developer tools": ["developer tool", "dev tool", "sdk", "api platform", "devx"],
        "ai infrastructure": ["ai infrastructure", "ml infrastructure", "mlops", "ai platform"],
    }

    matched_domains = []
    for interest in candidate.domain_interests:
        interest_lower = interest.lower()
        keywords = domain_keywords.get(interest_lower, [interest_lower])
        if any(kw in combined for kw in keywords):
            matched_domains.append(interest)

    if not matched_domains:
        return 40.0, "Job domain doesn't clearly match candidate interests"

    ratio = len(matched_domains) / len(candidate.domain_interests)
    score = 60.0 + ratio * 40.0
    return score, f"Domain match: {', '.join(matched_domains)}"


def _build_strengths(
    req_score: float,
    exp_score: float,
    role_score: float,
    loc_score: float,
    matched_count: int,
    total_required: int,
) -> list[str]:
    """Build list of candidate strengths for this job."""
    strengths = []
    if req_score >= 80:
        strengths.append(f"Strong skills match ({matched_count}/{total_required} required skills)")
    if exp_score >= 90:
        strengths.append("Experience level aligns well")
    if role_score >= 85:
        strengths.append("Job title closely matches target roles")
    if loc_score >= 90:
        strengths.append("Location/remote preference satisfied")
    return strengths


def _build_concerns(
    missing_required: list[str],
    missing_preferred: list[str],
    exp_score: float,
    experience_gap: str | None,
    location_score: float,
    role_score: float,
) -> list[str]:
    """Build list of concerns for this job."""
    concerns = []
    if missing_required:
        concerns.append(f"Missing required skills: {', '.join(missing_required[:5])}")
    if experience_gap:
        concerns.append(f"Experience: {experience_gap}")
    if location_score < 50:
        concerns.append("Location may not align with preferences")
    if role_score < 50:
        concerns.append("Job title differs significantly from target roles")
    if len(missing_preferred) > 3:
        concerns.append(f"Missing {len(missing_preferred)} preferred skills")
    return concerns
