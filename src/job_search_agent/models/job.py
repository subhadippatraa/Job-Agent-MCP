"""Canonical Job schema — the normalized representation of any job posting."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class RemoteType(enum.StrEnum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class EmploymentType(enum.StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"
    UNKNOWN = "unknown"


class JobStatus(enum.StrEnum):
    DISCOVERED = "discovered"
    ANALYZED = "analyzed"
    SHORTLISTED = "shortlisted"
    PREPARED = "prepared"
    APPLIED = "applied"
    ASSESSMENT = "assessment"
    RECRUITER_SCREEN = "recruiter_screen"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"
    WITHDRAWN = "withdrawn"
    SKIPPED = "skipped"


class ATSProvider(enum.StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    ICIMS = "icims"
    TALEO = "taleo"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class Job(BaseModel):
    """Canonical normalized job representation.

    Missing values remain None — never infer salary, experience,
    or other facts that aren't explicitly stated in the posting.
    """

    id: str | None = Field(default=None, description="Internal UUID")
    external_id: str | None = Field(default=None, description="ID from the source ATS")

    # Core
    company: str = Field(description="Company name")
    title: str = Field(description="Original job title as posted")
    normalized_title: str | None = Field(
        default=None,
        description="Cleaned/normalized title for matching",
    )

    # Location
    location: str | None = Field(default=None, description="Location as listed")
    country: str | None = Field(default=None, description="Country code or name")
    remote_type: RemoteType = Field(default=RemoteType.UNKNOWN)
    employment_type: EmploymentType = Field(default=EmploymentType.UNKNOWN)

    # Description
    description: str | None = Field(
        default=None,
        description="Full job description text (HTML stripped)",
    )
    description_html: str | None = Field(
        default=None,
        description="Original HTML description for reference",
    )
    requirements: str | None = Field(default=None, description="Requirements section text")

    # Skills
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    # Experience
    min_experience: int | None = Field(
        default=None,
        description="Minimum years of experience required (null if not stated)",
    )
    max_experience: int | None = Field(
        default=None,
        description="Maximum years of experience stated (null if not stated)",
    )

    # Compensation — never inferred
    salary_min: float | None = Field(default=None)
    salary_max: float | None = Field(default=None)
    salary_currency: str | None = Field(default=None)

    # Source tracking
    source: str | None = Field(default=None, description="Provider name (greenhouse, lever, etc)")
    source_url: str | None = Field(default=None, description="URL where the job was found")
    canonical_url: str | None = Field(default=None, description="Deduplicated canonical URL")
    application_url: str | None = Field(default=None, description="Direct application link")
    ats_provider: ATSProvider = Field(default=ATSProvider.UNKNOWN)

    # Timestamps
    posted_at: datetime | None = Field(default=None, description="When the job was posted")
    discovered_at: datetime | None = Field(
        default=None,
        description="When we first found this job",
    )
    updated_at: datetime | None = Field(default=None)

    # Matching (populated after scoring)
    match_score: float | None = Field(
        default=None,
        description="Candidate match score 0-100",
    )
    status: JobStatus = Field(default=JobStatus.DISCOVERED)
    skip_reason: str | None = Field(default=None)

    # Department / team
    department: str | None = Field(default=None)
    team: str | None = Field(default=None)

    model_config = {"use_enum_values": True}
