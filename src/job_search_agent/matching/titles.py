"""Job title similarity scoring."""

from __future__ import annotations

import re

from job_search_agent.providers.greenhouse import _normalize_title

# Groups of equivalent/similar titles
TITLE_GROUPS: list[set[str]] = [
    {"ai engineer", "artificial intelligence engineer", "machine learning engineer", "ml engineer"},
    {"generative ai engineer", "genai engineer", "gen ai engineer", "llm engineer"},
    {"rag engineer", "retrieval engineer", "search engineer"},
    {"agentic ai engineer", "ai agent engineer", "agent engineer"},
    {"applied ai engineer", "applied ml engineer", "applied machine learning engineer"},
    {"ai backend engineer", "backend ai engineer", "ai platform engineer"},
    {"python engineer", "python developer", "python backend engineer"},
    {"data scientist", "senior data scientist", "lead data scientist"},
    {"data engineer", "senior data engineer"},
    {"software engineer", "software developer", "sde", "swe"},
    {"full stack engineer", "fullstack engineer", "full-stack engineer", "full stack developer"},
    {"devops engineer", "site reliability engineer", "sre", "platform engineer"},
    {"frontend engineer", "frontend developer", "ui engineer", "ui developer"},
]


def compute_title_similarity(
    candidate_target_roles: list[str],
    job_title: str,
) -> tuple[float, str]:
    """Score how well a job title matches the candidate's target roles.

    Returns (score 0-100, explanation).
    """
    if not candidate_target_roles:
        return 50.0, "No target roles specified by candidate"

    job_normalized = _normalize_title(job_title)

    best_score = 0.0
    best_detail = ""

    for target in candidate_target_roles:
        target_normalized = _normalize_title(target)

        # Exact match
        if target_normalized == job_normalized:
            return 100.0, f"Exact role match: '{job_title}' matches target '{target}'"

        # Substring match
        if target_normalized in job_normalized or job_normalized in target_normalized:
            score = 90.0
            if score > best_score:
                best_score = score
                best_detail = f"Close match: '{job_title}' contains/matches target '{target}'"
            continue

        # Title group match
        target_group = _find_title_group(target_normalized)
        job_group = _find_title_group(job_normalized)

        if target_group is not None and target_group == job_group:
            score = 85.0
            if score > best_score:
                best_score = score
                best_detail = f"Same role category: '{job_title}' is in same group as '{target}'"
            continue

        # Keyword overlap
        target_words = set(target_normalized.split())
        job_words = set(job_normalized.split())
        common = target_words & job_words
        if common:
            overlap_ratio = len(common) / max(len(target_words), len(job_words))
            score = 50.0 + overlap_ratio * 40.0
            if score > best_score:
                best_score = score
                best_detail = f"Partial match: '{job_title}' shares keywords with '{target}' ({', '.join(common)})"

    if best_score == 0.0:
        return 30.0, f"Low title match: '{job_title}' doesn't match any target role"

    return best_score, best_detail


def _find_title_group(normalized_title: str) -> int | None:
    """Find which title group a normalized title belongs to."""
    for i, group in enumerate(TITLE_GROUPS):
        if normalized_title in group:
            return i
        # Also check if any group entry is a substring
        for entry in group:
            if entry in normalized_title or normalized_title in entry:
                return i
    return None
