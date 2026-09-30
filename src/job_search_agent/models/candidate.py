"""Candidate profile schema and YAML loader."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class WorkHistoryEntry(BaseModel):
    """A single position in the candidate's work history."""

    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = Field(default=None, description="None means 'present'")
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    """A project the candidate has worked on."""

    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class EducationEntry(BaseModel):
    """An education credential."""

    institution: str
    degree: str | None = None
    field: str | None = None
    year: int | None = None


class SalaryExpectation(BaseModel):
    """Salary expectations — optional and private."""

    min: float | None = None
    max: float | None = None
    currency: str = "INR"
    period: str = "annual"


class CandidateProfile(BaseModel):
    """Full candidate profile loaded from YAML.

    Sensitive fields are optional — the system never invents
    values that aren't present in the profile.
    """

    # Identity
    name: str
    email: str | None = None
    phone: str | None = None
    current_location: str | None = None

    # Experience
    years_experience: float | None = Field(
        default=None,
        description="Total years of relevant experience",
    )

    # Target roles
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    preferred_countries: list[str] = Field(default_factory=list)
    remote_preference: str = Field(
        default="flexible",
        description="'remote_only', 'onsite_only', 'hybrid', 'flexible'",
    )

    # Skills
    skills: list[str] = Field(
        default_factory=list,
        description="All skills combined (for simple matching)",
    )
    primary_skills: list[str] = Field(
        default_factory=list,
        description="Core skills the candidate is strongest in",
    )
    secondary_skills: list[str] = Field(
        default_factory=list,
        description="Additional/supporting skills",
    )

    # History
    work_history: list[WorkHistoryEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)

    # Sensitive — optional, never guessed
    work_authorization: str | None = Field(
        default=None,
        description="e.g., 'citizen', 'work_permit', 'visa_required'",
    )
    notice_period: str | None = Field(
        default=None,
        description="e.g., '30 days', 'immediate'",
    )
    salary_expectation: SalaryExpectation | None = None

    # Links
    links: dict[str, str] = Field(
        default_factory=dict,
        description="e.g., {'github': 'https://...', 'linkedin': 'https://...'}",
    )

    # Certifications
    certifications: list[str] = Field(default_factory=list)

    # Domain interests
    domain_interests: list[str] = Field(
        default_factory=list,
        description="e.g., ['AI/ML', 'Backend', 'DevOps']",
    )

    @property
    def all_skills(self) -> list[str]:
        """Combined and deduplicated skill list."""
        seen: set[str] = set()
        result: list[str] = []
        for skill in [*self.primary_skills, *self.secondary_skills, *self.skills]:
            key = skill.lower().strip()
            if key and key not in seen:
                seen.add(key)
                result.append(skill.strip())
        return result


def load_candidate_profile(path: str | Path) -> CandidateProfile:
    """Load a candidate profile from a YAML file.

    Raises FileNotFoundError if the profile doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Candidate profile not found at {path}. "
            f"Copy profile/candidate.example.yaml to {path} and fill in your details."
        )

    with open(path) as f:
        data = yaml.safe_load(f)

    return CandidateProfile(**data)
