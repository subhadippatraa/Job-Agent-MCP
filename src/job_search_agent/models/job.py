"""Canonical Job schema — the normalized representation of any job posting."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RemoteType(str, enum.Enum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class EmploymentType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"
    UNKNOWN = "unknown"


class JobStatus(str, enum.Enum):
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


class ATSProvider(str, enum.Enum):
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

    id: Optional[str] = Field(default=None, description="Internal UUID")
    external_id: Optional[str] = Field(default=None, description="ID from the source ATS")

    # Core
    company: str = Field(description="Company name")
    title: str = Field(description="Original job title as posted")
    normalized_title: Optional[str] = Field(
        default=None,
        description="Cleaned/normalized title for matching",
    )

    # Location
    location: Optional[str] = Field(default=None, description="Location as listed")
    country: Optional[str] = Field(default=None, description="Country code or name")
    remote_type: RemoteType = Field(default=RemoteType.UNKNOWN)
    employment_type: EmploymentType = Field(default=EmploymentType.UNKNOWN)

    # Description
    description: Optional[str] = Field(
        default=None,
        description="Full job description text (HTML stripped)",
    )
    description_html: Optional[str] = Field(
        default=None,
        description="Original HTML description for reference",
    )
    requirements: Optional[str] = Field(default=None, description="Requirements section text")

    # Skills
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    # Experience
    min_experience: Optional[int] = Field(
        default=None,
        description="Minimum years of experience required (null if not stated)",
    )
    max_experience: Optional[int] = Field(
        default=None,
        description="Maximum years of experience stated (null if not stated)",
    )

    # Compensation — never inferred
    salary_min: Optional[float] = Field(default=None)
    salary_max: Optional[float] = Field(default=None)
    salary_currency: Optional[str] = Field(default=None)

    # Source tracking
    source: Optional[str] = Field(default=None, description="Provider name (greenhouse, lever, etc)")
    source_url: Optional[str] = Field(default=None, description="URL where the job was found")
    canonical_url: Optional[str] = Field(default=None, description="Deduplicated canonical URL")
    application_url: Optional[str] = Field(default=None, description="Direct application link")
    ats_provider: ATSProvider = Field(default=ATSProvider.UNKNOWN)

    # Timestamps
    posted_at: Optional[datetime] = Field(default=None, description="When the job was posted")
    discovered_at: Optional[datetime] = Field(
        default=None,
        description="When we first found this job",
    )
    updated_at: Optional[datetime] = Field(default=None)

    # Matching (populated after scoring)
    match_score: Optional[float] = Field(
        default=None,
        description="Candidate match score 0-100",
    )
    status: JobStatus = Field(default=JobStatus.DISCOVERED)
    skip_reason: Optional[str] = Field(default=None)

    # Department / team
    department: Optional[str] = Field(default=None)
    team: Optional[str] = Field(default=None)

    model_config = {"use_enum_values": True}
