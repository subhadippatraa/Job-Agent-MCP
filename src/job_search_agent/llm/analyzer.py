"""LLM-enhanced job description analysis.

Uses the configured LLM to extract structured requirements, summarize JDs,
and compare jobs semantically — things regex/keyword matching can't do well.

Gracefully degrades: if no LLM is configured, returns None so the caller
falls back to deterministic extraction.
"""

from __future__ import annotations

import json

from job_search_agent.llm.base import LLMProvider, NoLLMProvider
from job_search_agent.logging import get_logger

logger = get_logger(__name__)

# ── Prompts ──────────────────────────────────────────────────────────────────

_EXTRACT_SYSTEM = """\
You are a structured data extraction engine for job postings.
Extract ONLY what is explicitly stated. Never infer or guess.
Respond with valid JSON only — no markdown fences, no explanation."""

_EXTRACT_PROMPT = """\
Analyze this job description and extract structured data.
Return a JSON object with these keys:

{{
  "title": "exact job title",
  "seniority_level": "intern|junior|mid|senior|staff|principal|director|vp|unknown",
  "employment_type": "full_time|part_time|contract|internship|unknown",
  "required_skills": ["list of explicitly required skills/technologies"],
  "preferred_skills": ["list of nice-to-have skills"],
  "min_experience_years": null or integer,
  "max_experience_years": null or integer,
  "education": "required education level or null",
  "remote_type": "remote|hybrid|onsite|unknown",
  "location": "location or null",
  "salary_min": null or number,
  "salary_max": null or number,
  "salary_currency": null or "USD",
  "responsibilities": ["top 5 key responsibilities"],
  "qualifications": ["top 5 key qualifications"],
  "team_info": "brief team/org description or null",
  "tech_stack": ["specific technologies/tools mentioned"],
  "red_flags": ["any concerning items like unpaid trial, excessive hours, etc."],
  "ai_ml_relevance": 0-100
}}

Job Description:
{description}"""

_COMPARE_SYSTEM = """\
You are a job comparison analyst. Compare jobs objectively based on the data provided.
Never invent information. Respond with valid JSON only — no markdown fences."""

_COMPARE_PROMPT = """\
Compare these two jobs for a candidate with these skills: {skills}
Target roles: {roles}
Experience: {experience} years

Job A:
  Company: {job_a_company}
  Title: {job_a_title}
  Location: {job_a_location}
  Required: {job_a_required}
  Preferred: {job_a_preferred}
  Experience: {job_a_experience}
  Description snippet: {job_a_desc}

Job B:
  Company: {job_b_company}
  Title: {job_b_title}
  Location: {job_b_location}
  Required: {job_b_required}
  Preferred: {job_b_preferred}
  Experience: {job_b_experience}
  Description snippet: {job_b_desc}

Return a JSON object:
{{
  "recommendation": "A" or "B" or "both" or "neither",
  "reasoning": "2-3 sentence explanation",
  "job_a_strengths": ["strengths for this candidate"],
  "job_a_concerns": ["concerns for this candidate"],
  "job_b_strengths": ["strengths for this candidate"],
  "job_b_concerns": ["concerns for this candidate"],
  "skill_overlap": ["skills that match both jobs"],
  "growth_potential": "which job offers better growth for this candidate and why"
}}"""

_SUMMARIZE_SYSTEM = """\
You are a concise job posting summarizer for job seekers.
Focus on what matters for application decisions. Be brief and factual."""

_SUMMARIZE_PROMPT = """\
Summarize this job posting in 4-6 bullet points covering:
- Role and core responsibilities
- Must-have skills/experience
- Nice-to-have skills
- Key things a candidate should know before applying

Job Description:
{description}"""


async def llm_extract_requirements(
    llm: LLMProvider,
    description: str,
) -> dict | None:
    """Use LLM to extract structured requirements from a job description.

    Returns extracted data dict, or None if LLM is unavailable.
    Falls back gracefully when no LLM is configured.
    """
    if isinstance(llm, NoLLMProvider):
        return None

    # Truncate very long descriptions to stay within token limits
    desc_truncated = description[:6000] if len(description) > 6000 else description

    try:
        raw = await llm.complete(
            prompt=_EXTRACT_PROMPT.format(description=desc_truncated),
            system=_EXTRACT_SYSTEM,
            max_tokens=1500,
            temperature=0.1,
        )

        # Parse JSON — handle potential markdown fences
        cleaned = _clean_json_response(raw)
        result = json.loads(cleaned)

        if not isinstance(result, dict):
            logger.warning("llm_extract_not_dict", type=type(result).__name__)
            return None

        logger.info("llm_extract_success", skills_found=len(result.get("required_skills", [])))
        return result

    except json.JSONDecodeError as e:
        logger.warning("llm_extract_json_error", error=str(e), raw_length=len(raw))
        return None
    except Exception as e:
        logger.error("llm_extract_error", error=str(e))
        return None


async def llm_compare_jobs(
    llm: LLMProvider,
    job_a: dict,
    job_b: dict,
    candidate_skills: list[str],
    candidate_roles: list[str],
    candidate_experience: float | None,
) -> dict | None:
    """Semantically compare two jobs for a candidate using LLM.

    Returns comparison dict, or None if LLM is unavailable.
    """
    if isinstance(llm, NoLLMProvider):
        return None

    try:
        prompt = _COMPARE_PROMPT.format(
            skills=", ".join(candidate_skills[:15]),
            roles=", ".join(candidate_roles[:5]),
            experience=candidate_experience or "unknown",
            job_a_company=job_a.get("company", "Unknown"),
            job_a_title=job_a.get("title", "Unknown"),
            job_a_location=job_a.get("location", "Not specified"),
            job_a_required=", ".join(job_a.get("required_skills", [])[:10]),
            job_a_preferred=", ".join(job_a.get("preferred_skills", [])[:5]),
            job_a_experience=f"{job_a.get('min_experience', '?')}-{job_a.get('max_experience', '?')}yr",
            job_a_desc=(job_a.get("description", "") or "")[:800],
            job_b_company=job_b.get("company", "Unknown"),
            job_b_title=job_b.get("title", "Unknown"),
            job_b_location=job_b.get("location", "Not specified"),
            job_b_required=", ".join(job_b.get("required_skills", [])[:10]),
            job_b_preferred=", ".join(job_b.get("preferred_skills", [])[:5]),
            job_b_experience=f"{job_b.get('min_experience', '?')}-{job_b.get('max_experience', '?')}yr",
            job_b_desc=(job_b.get("description", "") or "")[:800],
        )

        raw = await llm.complete(
            prompt=prompt,
            system=_COMPARE_SYSTEM,
            max_tokens=1000,
            temperature=0.2,
        )

        cleaned = _clean_json_response(raw)
        result = json.loads(cleaned)

        if not isinstance(result, dict):
            return None

        logger.info("llm_compare_success", recommendation=result.get("recommendation"))
        return result

    except json.JSONDecodeError as e:
        logger.warning("llm_compare_json_error", error=str(e))
        return None
    except Exception as e:
        logger.error("llm_compare_error", error=str(e))
        return None


async def llm_summarize_job(
    llm: LLMProvider,
    description: str,
) -> str | None:
    """Generate a concise summary of a job posting using LLM.

    Returns summary string, or None if LLM is unavailable.
    """
    if isinstance(llm, NoLLMProvider):
        return None

    desc_truncated = description[:5000] if len(description) > 5000 else description

    try:
        result = await llm.complete(
            prompt=_SUMMARIZE_PROMPT.format(description=desc_truncated),
            system=_SUMMARIZE_SYSTEM,
            max_tokens=500,
            temperature=0.3,
        )
        return result.strip() if result else None
    except Exception as e:
        logger.error("llm_summarize_error", error=str(e))
        return None


def merge_llm_extraction(
    regex_skills: tuple[list[str], list[str]],
    regex_experience: tuple[int | None, int | None],
    llm_data: dict | None,
) -> tuple[list[str], list[str], int | None, int | None, dict]:
    """Merge LLM extraction results with regex-based extraction.

    LLM results augment regex — they don't replace. The union of both
    is used, with LLM-only skills marked as llm_source.

    Returns (required_skills, preferred_skills, min_exp, max_exp, metadata).
    """
    req_regex, pref_regex = regex_skills
    min_exp_regex, max_exp_regex = regex_experience
    metadata: dict = {}

    if llm_data is None:
        return req_regex, pref_regex, min_exp_regex, max_exp_regex, metadata

    # Merge skills — union, preserving order
    llm_required = llm_data.get("required_skills", [])
    llm_preferred = llm_data.get("preferred_skills", [])

    req_set = {s.lower() for s in req_regex}
    required_merged = list(req_regex)
    llm_only_required = []
    for skill in llm_required:
        if skill.lower() not in req_set:
            required_merged.append(skill)
            llm_only_required.append(skill)
            req_set.add(skill.lower())

    pref_set = {s.lower() for s in pref_regex} | req_set
    preferred_merged = list(pref_regex)
    llm_only_preferred = []
    for skill in llm_preferred:
        if skill.lower() not in pref_set:
            preferred_merged.append(skill)
            llm_only_preferred.append(skill)
            pref_set.add(skill.lower())

    # Merge experience — LLM fills gaps, doesn't override
    min_exp = min_exp_regex
    max_exp = max_exp_regex
    if min_exp is None and llm_data.get("min_experience_years") is not None:
        min_exp = llm_data["min_experience_years"]
    if max_exp is None and llm_data.get("max_experience_years") is not None:
        max_exp = llm_data["max_experience_years"]

    # Metadata for transparency
    metadata = {
        "llm_enhanced": True,
        "llm_only_required_skills": llm_only_required,
        "llm_only_preferred_skills": llm_only_preferred,
        "seniority_level": llm_data.get("seniority_level"),
        "responsibilities": llm_data.get("responsibilities", []),
        "qualifications": llm_data.get("qualifications", []),
        "tech_stack": llm_data.get("tech_stack", []),
        "team_info": llm_data.get("team_info"),
        "education": llm_data.get("education"),
        "red_flags": llm_data.get("red_flags", []),
        "ai_ml_relevance": llm_data.get("ai_ml_relevance"),
    }

    return required_merged, preferred_merged, min_exp, max_exp, metadata


def _clean_json_response(raw: str) -> str:
    """Clean LLM response to extract valid JSON."""
    text = raw.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Find the JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    return text
