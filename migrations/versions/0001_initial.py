"""Initial job agent schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(255)),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("normalized_title", sa.String(500)),
        sa.Column("location", sa.String(500)),
        sa.Column("country", sa.String(100)),
        sa.Column("remote_type", sa.String(20), nullable=False),
        sa.Column("employment_type", sa.String(20), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("description_html", sa.Text()),
        sa.Column("requirements", sa.Text()),
        sa.Column("required_skills_json", sa.Text()),
        sa.Column("preferred_skills_json", sa.Text()),
        sa.Column("min_experience", sa.Integer()),
        sa.Column("max_experience", sa.Integer()),
        sa.Column("salary_min", sa.Float()),
        sa.Column("salary_max", sa.Float()),
        sa.Column("salary_currency", sa.String(10)),
        sa.Column("source", sa.String(50)),
        sa.Column("source_url", sa.Text()),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("application_url", sa.Text()),
        sa.Column("ats_provider", sa.String(20), nullable=False),
        sa.Column("posted_at", sa.DateTime()),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("match_score", sa.Float()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("skip_reason", sa.Text()),
        sa.Column("department", sa.String(255)),
        sa.Column("team", sa.String(255)),
        sa.UniqueConstraint("canonical_url", name="uq_jobs_canonical_url"),
    )
    for column in ("company", "status", "discovered_at", "match_score"):
        op.create_index(f"ix_jobs_{column}", "jobs", [column])

    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("applied_at", sa.DateTime()),
        sa.Column("resume_version", sa.String(100)),
        sa.Column("application_url", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_job_id", "applications", ["job_id"])

    op.create_table(
        "status_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False
        ),
        sa.Column("old_status", sa.String(20), nullable=False),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text()),
    )
    op.create_table(
        "job_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(30), nullable=False),
        sa.Column("experience_match", sa.Boolean(), nullable=False),
        sa.Column("location_match", sa.Boolean(), nullable=False),
        sa.Column("matched_skills_json", sa.Text()),
        sa.Column("missing_required_json", sa.Text()),
        sa.Column("missing_preferred_json", sa.Text()),
        sa.Column("strengths_json", sa.Text()),
        sa.Column("concerns_json", sa.Text()),
        sa.Column("breakdown_json", sa.Text()),
        sa.Column("experience_gap", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])
    op.create_index("ix_job_matches_score", "job_matches", ["score"])
    op.create_table(
        "search_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("query_json", sa.Text()),
        sa.Column("providers_used", sa.Text()),
        sa.Column("total_results", sa.Integer(), nullable=False),
        sa.Column("new_jobs", sa.Integer(), nullable=False),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False),
        sa.Column("errors_json", sa.Text()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("search_runs")
    op.drop_table("job_matches")
    op.drop_table("status_history")
    op.drop_table("applications")
    op.drop_table("jobs")
