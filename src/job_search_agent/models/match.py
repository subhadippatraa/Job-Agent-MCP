"""Match result models — structured, explainable scoring output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillMatch(BaseModel):
    """Detailed skill matching breakdown."""

    skill: str
    matched: bool
    match_type: str = Field(
        description="'exact', 'alias', 'partial', 'missing'",
    )
    candidate_evidence: str | None = Field(
        default=None,
        description="Evidence from resume/profile supporting this skill",
    )


class ScoreBreakdown(BaseModel):
    """Detailed breakdown of how the match score was computed."""

    required_skills_score: float = Field(description="0-100 score for required skills")
    required_skills_weight: float = Field(description="Weight applied (e.g., 0.35)")
    required_skills_detail: str = Field(
        default="", description="e.g., '8/10 required skills matched'"
    )

    preferred_skills_score: float = 0.0
    preferred_skills_weight: float = 0.10
    preferred_skills_detail: str = ""

    experience_score: float = 0.0
    experience_weight: float = 0.20
    experience_detail: str = ""

    role_similarity_score: float = 0.0
    role_similarity_weight: float = 0.15
    role_similarity_detail: str = ""

    location_score: float = 0.0
    location_weight: float = 0.10
    location_detail: str = ""

    domain_score: float = 0.0
    domain_weight: float = 0.10
    domain_detail: str = ""


class MatchResult(BaseModel):
    """Complete match result between a job and the candidate.

    The score is deterministic and explainable — every point
    is accounted for in the breakdown.
    """

    job_id: str | None = None
    score: float = Field(description="Composite score 0-100")
    recommendation: str = Field(
        description="'exceptional_match', 'strong_match', 'good_match', 'possible_match', 'low_match'",
    )

    # Quick checks
    experience_match: bool = True
    location_match: bool = True

    # Skill details
    matched_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    skill_details: list[SkillMatch] = Field(default_factory=list)

    # Experience
    experience_gap: str | None = Field(
        default=None,
        description="Description of experience gap, if any",
    )

    # Strengths and concerns
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)

    # Evidence from resume
    resume_evidence: list[str] = Field(default_factory=list)

    # Full breakdown
    breakdown: ScoreBreakdown | None = None

    @staticmethod
    def classify_score(score: float) -> str:
        """Classify a numeric score into a recommendation label."""
        if score >= 90:
            return "exceptional_match"
        elif score >= 80:
            return "strong_match"
        elif score >= 70:
            return "good_match"
        elif score >= 60:
            return "possible_match"
        else:
            return "low_match"
