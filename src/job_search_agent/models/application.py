"""Application tracking models."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class ApplicationStatus(enum.StrEnum):
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


class Application(BaseModel):
    """An application record tracking a candidate's interaction with a job."""

    id: str | None = None
    job_id: str
    candidate_id: str | None = None

    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    applied_at: datetime | None = None
    resume_version: str | None = None
    application_url: str | None = None
    notes: str | None = None
    source: str | None = None

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"use_enum_values": True}


class ApplicationStatusChange(BaseModel):
    """A single status change in an application's history."""

    id: str | None = None
    application_id: str
    old_status: str
    new_status: str
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    notes: str | None = None


class ApplicationPrep(BaseModel):
    """Application preparation package returned by prepare_application.

    Contains everything the candidate needs to apply, without fabricating
    any qualifications or submitting anything automatically.
    """

    job_id: str
    company: str
    title: str

    # Match context
    match_score: float | None = None
    recommendation: str | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)

    # Resume guidance
    relevant_resume_bullets: list[str] = Field(
        default_factory=list,
        description="Resume evidence most relevant to this job",
    )
    skills_to_emphasize: list[str] = Field(default_factory=list)
    potential_gaps: list[str] = Field(default_factory=list)

    # Key JD requirements
    important_requirements: list[str] = Field(default_factory=list)

    # Communication
    suggested_recruiter_message: str | None = None
    suggested_cover_letter_points: list[str] = Field(default_factory=list)
    likely_screening_questions: list[str] = Field(default_factory=list)

    # Fields that must NOT be guessed
    requires_user_input: list[str] = Field(
        default_factory=list,
        description="Sensitive fields the system cannot answer automatically",
    )

    # Application checklist
    application_checklist: list[str] = Field(default_factory=list)

    # Application URL
    application_url: str | None = None
