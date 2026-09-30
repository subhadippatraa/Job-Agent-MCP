"""Resume evidence extraction — maps skills to supporting resume text."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_search_agent.resume.parser import ResumeData


def extract_evidence_for_skills(
    resume: ResumeData,
    skills: list[str],
) -> dict[str, list[str]]:
    """Extract resume evidence for each skill.

    Returns a mapping like:
        {
            "langgraph": ["Built 4 of the assistant's 6 agents with LangGraph orchestration."],
            "fastapi": ["Developed RESTful API with FastAPI serving 10k+ requests/day."],
        }
    """
    return resume.build_evidence_map(skills)


def get_relevant_bullets(
    resume: ResumeData,
    job_required_skills: list[str],
    job_preferred_skills: list[str],
    max_bullets: int = 10,
) -> list[str]:
    """Get the most relevant resume bullets for a specific job.

    Prioritizes evidence for required skills, then preferred.
    """
    seen: set[str] = set()
    bullets: list[str] = []

    # Required skills first
    for skill in job_required_skills:
        for evidence in resume.find_evidence(skill):
            if evidence not in seen and len(bullets) < max_bullets:
                seen.add(evidence)
                bullets.append(evidence)

    # Then preferred skills
    for skill in job_preferred_skills:
        for evidence in resume.find_evidence(skill):
            if evidence not in seen and len(bullets) < max_bullets:
                seen.add(evidence)
                bullets.append(evidence)

    return bullets
