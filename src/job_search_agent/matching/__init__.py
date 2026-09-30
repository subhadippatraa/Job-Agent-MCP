"""Matching engine — skill matching, experience scoring, composite scoring."""

from job_search_agent.matching.experience import compute_experience_score
from job_search_agent.matching.scorer import score_job
from job_search_agent.matching.skills import (
    canonicalize_skill,
    compute_skill_score,
    match_skills,
)
from job_search_agent.matching.titles import compute_title_similarity

__all__ = [
    "canonicalize_skill",
    "compute_experience_score",
    "compute_skill_score",
    "compute_title_similarity",
    "match_skills",
    "score_job",
]
