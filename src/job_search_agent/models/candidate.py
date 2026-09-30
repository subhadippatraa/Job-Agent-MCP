"""Candidate profile schema and YAML loader."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class WorkHistoryEntry(BaseModel):
    """A single position in the candidate's work history."""

    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = Field(default=None, description="None means 'present'")
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    """A project the candidate has worked on."""

    name: str
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    url: Optional[str] = None


class EducationEntry(BaseModel):
    """An education credential."""

    institution: str
    degree: Optional[str] = None
    field: Optional[str] = None
    year: Optional[int] = None


class SalaryExpectation(BaseModel):
    """Salary expectations — optional and private."""

    min: Optional[float] = None
    max: Optional[float] = None
    currency: str = "INR"
    period: str = "annual"


class CandidateProfile(BaseModel):
    """Full candidate profile loaded from YAML.

    Sensitive fields are optional — the system never invents
    values that aren't present in the profile.
    """

    # Identity
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    current_location: Optional[str] = None

    # Experience
    years_experience: Optional[float] = Field(
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
    work_authorization: Optional[str] = Field(
        default=None,
        description="e.g., 'citizen', 'work_permit', 'visa_required'",
    )
    notice_period: Optional[str] = Field(
        default=None,
        description="e.g., '30 days', 'immediate'",
    )
    salary_expectation: Optional[SalaryExpectation] = None

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

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    return CandidateProfile(**data)
