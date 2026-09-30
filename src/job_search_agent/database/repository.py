"""Database repository — async CRUD operations for all entities."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, desc, func, or_, select, update

from job_search_agent.database.models import (
    ApplicationRow,
    JobMatchRow,
    JobRow,
    SearchRunRow,
    StatusHistoryRow,
)
from job_search_agent.models.application import Application
from job_search_agent.models.job import Job, JobStatus
from job_search_agent.models.match import MatchResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _job_row_to_model(row: JobRow) -> Job:
    """Convert a database row to a Job Pydantic model."""
    return Job(
        id=row.id,
        external_id=row.external_id,
        company=row.company,
        title=row.title,
        normalized_title=row.normalized_title,
        location=row.location,
        country=row.country,
        remote_type=row.remote_type,
        employment_type=row.employment_type,
        description=row.description,
        description_html=row.description_html,
        requirements=row.requirements,
        required_skills=json.loads(row.required_skills_json) if row.required_skills_json else [],
        preferred_skills=json.loads(row.preferred_skills_json) if row.preferred_skills_json else [],
        min_experience=row.min_experience,
        max_experience=row.max_experience,
        salary_min=row.salary_min,
        salary_max=row.salary_max,
        salary_currency=row.salary_currency,
        source=row.source,
        source_url=row.source_url,
        canonical_url=row.canonical_url,
        application_url=row.application_url,
        ats_provider=row.ats_provider,
        posted_at=row.posted_at,
        discovered_at=row.discovered_at,
        updated_at=row.updated_at,
        match_score=row.match_score,
        status=row.status,
        skip_reason=row.skip_reason,
        department=row.department,
        team=row.team,
    )


def _job_model_to_row(job: Job) -> JobRow:
    """Convert a Job Pydantic model to a database row."""
    return JobRow(
        id=job.id,
        external_id=job.external_id,
        company=job.company,
        title=job.title,
        normalized_title=job.normalized_title,
        location=job.location,
        country=job.country,
        remote_type=job.remote_type,
        employment_type=job.employment_type,
        description=job.description,
        description_html=job.description_html,
        requirements=job.requirements,
        required_skills_json=json.dumps(job.required_skills) if job.required_skills else None,
        preferred_skills_json=json.dumps(job.preferred_skills) if job.preferred_skills else None,
        min_experience=job.min_experience,
        max_experience=job.max_experience,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        source=job.source,
        source_url=job.source_url,
        canonical_url=job.canonical_url,
        application_url=job.application_url,
        ats_provider=job.ats_provider,
        posted_at=job.posted_at,
        discovered_at=job.discovered_at or datetime.utcnow(),
        status=job.status,
        skip_reason=job.skip_reason,
        department=job.department,
        team=job.team,
    )


class JobRepository:
    """Async repository for Job CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, job: Job) -> Job:
        """Insert or update a job. Generates ID if missing."""
        import uuid

        if not job.id:
            job.id = str(uuid.uuid4())

        row = _job_model_to_row(job)
        self.session.add(row)
        await self.session.flush()
        return _job_row_to_model(row)

    async def get_by_id(self, job_id: str) -> Job | None:
        """Get a single job by ID."""
        result = await self.session.execute(select(JobRow).where(JobRow.id == job_id))
        row = result.scalar_one_or_none()
        return _job_row_to_model(row) if row else None

    async def get_by_canonical_url(self, url: str) -> Job | None:
        """Find a job by its canonical URL (for duplicate detection)."""
        result = await self.session.execute(select(JobRow).where(JobRow.canonical_url == url))
        row = result.scalar_one_or_none()
        return _job_row_to_model(row) if row else None

    async def find_duplicate(
        self,
        company: str,
        title: str,
        location: str | None = None,
    ) -> Job | None:
        """Find a potential duplicate by company + normalized title."""
        conditions = [
            func.lower(JobRow.company) == company.lower(),
            func.lower(JobRow.title) == title.lower(),
        ]
        if location:
            conditions.append(func.lower(JobRow.location) == location.lower())

        result = await self.session.execute(select(JobRow).where(and_(*conditions)))
        row = result.scalar_one_or_none()
        return _job_row_to_model(row) if row else None

    async def search(
        self,
        keywords: list[str] | None = None,
        company: str | None = None,
        status: str | None = None,
        min_score: float | None = None,
        posted_after: datetime | None = None,
        limit: int = 50,
    ) -> list[Job]:
        """Search jobs with filters."""
        query = select(JobRow)
        conditions = []

        if keywords:
            kw_conditions = []
            for kw in keywords:
                pattern = f"%{kw}%"
                kw_conditions.append(
                    or_(
                        JobRow.title.ilike(pattern),
                        JobRow.description.ilike(pattern),
                        JobRow.company.ilike(pattern),
                    )
                )
            conditions.append(or_(*kw_conditions))

        if company:
            conditions.append(func.lower(JobRow.company) == company.lower())

        if status:
            conditions.append(JobRow.status == status)

        if min_score is not None:
            conditions.append(JobRow.match_score >= min_score)

        if posted_after:
            conditions.append(JobRow.discovered_at >= posted_after)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(JobRow.match_score), desc(JobRow.discovered_at))
        query = query.limit(limit)

        result = await self.session.execute(query)
        return [_job_row_to_model(row) for row in result.scalars().all()]

    async def update_status(
        self,
        job_id: str,
        status: str,
        skip_reason: str | None = None,
    ) -> bool:
        """Update a job's status."""
        values: dict = {"status": status, "updated_at": datetime.utcnow()}
        if skip_reason:
            values["skip_reason"] = skip_reason

        result = await self.session.execute(
            update(JobRow).where(JobRow.id == job_id).values(**values)
        )
        await self.session.flush()
        return result.rowcount > 0  # type: ignore[union-attr]

    async def update_match_score(self, job_id: str, score: float) -> bool:
        """Update a job's match score."""
        result = await self.session.execute(
            update(JobRow)
            .where(JobRow.id == job_id)
            .values(match_score=score, updated_at=datetime.utcnow())
        )
        await self.session.flush()
        return result.rowcount > 0  # type: ignore[union-attr]

    async def update_job(self, job: Job) -> bool:
        """Update a job's skills, experience, and other extracted data."""
        values: dict = {"updated_at": datetime.utcnow()}
        if job.required_skills:
            values["required_skills_json"] = json.dumps(job.required_skills)
        if job.preferred_skills:
            values["preferred_skills_json"] = json.dumps(job.preferred_skills)
        if job.min_experience is not None:
            values["min_experience"] = job.min_experience
        if job.max_experience is not None:
            values["max_experience"] = job.max_experience

        result = await self.session.execute(
            update(JobRow).where(JobRow.id == job.id).values(**values)
        )
        await self.session.flush()
        return result.rowcount > 0  # type: ignore[union-attr]

    async def get_stats(self) -> dict:
        """Get aggregate job statistics."""
        session = self.session

        total = await session.scalar(select(func.count(JobRow.id)))

        status_counts = {}
        for status in JobStatus:
            count = await session.scalar(
                select(func.count(JobRow.id)).where(JobRow.status == status.value)
            )
            status_counts[status.value] = count or 0

        avg_score = await session.scalar(
            select(func.avg(JobRow.match_score)).where(JobRow.match_score.isnot(None))
        )

        return {
            "total_jobs": total or 0,
            "by_status": status_counts,
            "average_match_score": round(avg_score, 1) if avg_score else None,
        }

    async def get_recent(
        self,
        since: datetime,
        min_score: float | None = None,
        limit: int = 10,
    ) -> list[Job]:
        """Get recent jobs, optionally filtered by minimum score."""
        query = select(JobRow).where(JobRow.discovered_at >= since)

        if min_score is not None:
            query = query.where(JobRow.match_score >= min_score)

        query = query.order_by(desc(JobRow.match_score), desc(JobRow.discovered_at))
        query = query.limit(limit)

        result = await self.session.execute(query)
        return [_job_row_to_model(row) for row in result.scalars().all()]


class ApplicationRepository:
    """Async repository for Application CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, app: Application) -> Application:
        """Create a new application record."""
        import uuid

        row = ApplicationRow(
            id=app.id or str(uuid.uuid4()),
            job_id=app.job_id,
            status=app.status,
            applied_at=app.applied_at,
            resume_version=app.resume_version,
            application_url=app.application_url,
            notes=app.notes,
            source=app.source,
        )
        self.session.add(row)
        await self.session.flush()

        app.id = row.id
        app.created_at = row.created_at
        return app

    async def get_by_job_id(self, job_id: str) -> Application | None:
        """Get application by job ID."""
        result = await self.session.execute(
            select(ApplicationRow).where(ApplicationRow.job_id == job_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None

        return Application(
            id=row.id,
            job_id=row.job_id,
            status=row.status,
            applied_at=row.applied_at,
            resume_version=row.resume_version,
            application_url=row.application_url,
            notes=row.notes,
            source=row.source,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def update_status(
        self,
        application_id: str,
        new_status: str,
        notes: str | None = None,
    ) -> bool:
        """Update application status and record history."""
        # Get current status
        result = await self.session.execute(
            select(ApplicationRow).where(ApplicationRow.id == application_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return False

        old_status = row.status

        # Update the application
        await self.session.execute(
            update(ApplicationRow)
            .where(ApplicationRow.id == application_id)
            .values(
                status=new_status,
                updated_at=datetime.utcnow(),
                applied_at=datetime.utcnow() if new_status == "applied" else row.applied_at,
            )
        )

        # Record status change
        history = StatusHistoryRow(
            application_id=application_id,
            old_status=old_status,
            new_status=new_status,
            notes=notes,
        )
        self.session.add(history)
        await self.session.flush()
        return True

    async def search(
        self,
        status: str | None = None,
        company: str | None = None,
        min_score: float | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search applications with filters. Returns joined job+application data."""
        query = select(ApplicationRow, JobRow).join(JobRow, ApplicationRow.job_id == JobRow.id)
        conditions = []

        if status:
            conditions.append(ApplicationRow.status == status)
        if company:
            conditions.append(func.lower(JobRow.company) == company.lower())
        if min_score is not None:
            conditions.append(JobRow.match_score >= min_score)
        if since:
            conditions.append(ApplicationRow.created_at >= since)
        if until:
            conditions.append(ApplicationRow.created_at <= until)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(ApplicationRow.updated_at)).limit(limit)
        result = await self.session.execute(query)

        apps = []
        for app_row, job_row in result.all():
            apps.append(
                {
                    "application": Application(
                        id=app_row.id,
                        job_id=app_row.job_id,
                        status=app_row.status,
                        applied_at=app_row.applied_at,
                        resume_version=app_row.resume_version,
                        application_url=app_row.application_url,
                        notes=app_row.notes,
                        source=app_row.source,
                        created_at=app_row.created_at,
                        updated_at=app_row.updated_at,
                    ).model_dump(mode="json"),
                    "job": {
                        "company": job_row.company,
                        "title": job_row.title,
                        "location": job_row.location,
                        "match_score": job_row.match_score,
                    },
                }
            )
        return apps

    async def check_company_applied(self, company: str) -> list[dict]:
        """Check if we've applied to a specific company before."""
        query = (
            select(ApplicationRow, JobRow)
            .join(JobRow, ApplicationRow.job_id == JobRow.id)
            .where(func.lower(JobRow.company) == company.lower())
        )
        result = await self.session.execute(query)

        return [
            {
                "job_title": job_row.title,
                "status": app_row.status,
                "applied_at": app_row.applied_at.isoformat() if app_row.applied_at else None,
                "job_id": job_row.id,
            }
            for app_row, job_row in result.all()
        ]

    async def get_stats(self) -> dict:
        """Get application statistics."""
        session = self.session

        total = await session.scalar(select(func.count(ApplicationRow.id)))

        status_counts = {}
        for status in [
            "discovered",
            "analyzed",
            "shortlisted",
            "prepared",
            "applied",
            "assessment",
            "recruiter_screen",
            "interview",
            "rejected",
            "offer",
            "withdrawn",
            "skipped",
        ]:
            count = await session.scalar(
                select(func.count(ApplicationRow.id)).where(ApplicationRow.status == status)
            )
            status_counts[status] = count or 0

        return {
            "total_applications": total or 0,
            "by_status": status_counts,
        }


class MatchRepository:
    """Async repository for cached match results."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, job_id: str, match: MatchResult) -> None:
        """Save a match result."""
        row = JobMatchRow(
            job_id=job_id,
            score=match.score,
            recommendation=match.recommendation,
            experience_match=match.experience_match,
            location_match=match.location_match,
            matched_skills_json=json.dumps(match.matched_skills),
            missing_required_json=json.dumps(match.missing_required_skills),
            missing_preferred_json=json.dumps(match.missing_preferred_skills),
            strengths_json=json.dumps(match.strengths),
            concerns_json=json.dumps(match.concerns),
            breakdown_json=match.breakdown.model_dump_json() if match.breakdown else None,
            experience_gap=match.experience_gap,
        )
        self.session.add(row)
        await self.session.flush()

    async def get_by_job_id(self, job_id: str) -> MatchResult | None:
        """Get cached match result for a job."""
        result = await self.session.execute(
            select(JobMatchRow)
            .where(JobMatchRow.job_id == job_id)
            .order_by(desc(JobMatchRow.created_at))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None

        from job_search_agent.models.match import ScoreBreakdown

        return MatchResult(
            job_id=job_id,
            score=row.score,
            recommendation=row.recommendation,
            experience_match=row.experience_match,
            location_match=row.location_match,
            matched_skills=json.loads(row.matched_skills_json) if row.matched_skills_json else [],
            missing_required_skills=json.loads(row.missing_required_json)
            if row.missing_required_json
            else [],
            missing_preferred_skills=json.loads(row.missing_preferred_json)
            if row.missing_preferred_json
            else [],
            strengths=json.loads(row.strengths_json) if row.strengths_json else [],
            concerns=json.loads(row.concerns_json) if row.concerns_json else [],
            breakdown=ScoreBreakdown.model_validate_json(row.breakdown_json)
            if row.breakdown_json
            else None,
            experience_gap=row.experience_gap,
        )


class SearchRunRepository:
    """Async repository for search run logging."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_search(
        self,
        query_params: dict,
        providers: list[str],
        total_results: int,
        new_jobs: int,
        duplicates_skipped: int,
        errors: list[dict] | None = None,
    ) -> str:
        """Log a search run."""
        import uuid

        row = SearchRunRow(
            id=str(uuid.uuid4()),
            query_json=json.dumps(query_params),
            providers_used=json.dumps(providers),
            total_results=total_results,
            new_jobs=new_jobs,
            duplicates_skipped=duplicates_skipped,
            errors_json=json.dumps(errors) if errors else None,
            completed_at=datetime.utcnow(),
        )
        self.session.add(row)
        await self.session.flush()
        return row.id
