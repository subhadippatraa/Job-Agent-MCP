"""SQLAlchemy ORM models for persistent storage."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    """Persistent job posting record."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Core
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Location
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_type: Mapped[str] = mapped_column(String(20), default="unknown")
    employment_type: Mapped[str] = mapped_column(String(20), default="unknown")

    # Description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Skills (JSON-serialized lists stored as text for SQLite compat)
    required_skills_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_skills_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Experience
    min_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Compensation
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Source
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_provider: Mapped[str] = mapped_column(String(20), default="unknown")

    # Timestamps
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Status
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="discovered")
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Department
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    applications: Mapped[list[ApplicationRow]] = relationship(back_populates="job")
    matches: Mapped[list[JobMatchRow]] = relationship(back_populates="job")

    __table_args__ = (
        Index("ix_jobs_company", "company"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_discovered_at", "discovered_at"),
        Index("ix_jobs_match_score", "match_score"),
        UniqueConstraint("canonical_url", name="uq_jobs_canonical_url"),
    )


class ApplicationRow(Base):
    """Application tracking record."""

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="discovered")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resume_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    application_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    job: Mapped[JobRow] = relationship(back_populates="applications")
    status_history: Mapped[list[StatusHistoryRow]] = relationship(back_populates="application")

    __table_args__ = (
        Index("ix_applications_status", "status"),
        UniqueConstraint("job_id", name="uq_applications_job_id"),
    )


class StatusHistoryRow(Base):
    """Application status change history."""

    __tablename__ = "status_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=False
    )
    old_status: Mapped[str] = mapped_column(String(20), nullable=False)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped[ApplicationRow] = relationship(back_populates="status_history")


class JobMatchRow(Base):
    """Cached match result between a job and the candidate."""

    __tablename__ = "job_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(30), nullable=False)
    experience_match: Mapped[bool] = mapped_column(Boolean, default=True)
    location_match: Mapped[bool] = mapped_column(Boolean, default=True)

    matched_skills_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_required_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_preferred_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    concerns_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    breakdown_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    experience_gap: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[JobRow] = relationship(back_populates="matches")

    __table_args__ = (
        Index("ix_job_matches_job_id", "job_id"),
        Index("ix_job_matches_score", "score"),
    )


class SearchRunRow(Base):
    """Log of each search execution for auditing."""

    __tablename__ = "search_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    query_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    providers_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_results: Mapped[int] = mapped_column(Integer, default=0)
    new_jobs: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
