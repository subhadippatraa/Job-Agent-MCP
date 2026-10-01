"""Enforce one application per job."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_index("ix_applications_job_id")
        batch_op.create_unique_constraint("uq_applications_job_id", ["job_id"])


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_constraint("uq_applications_job_id", type_="unique")
        batch_op.create_index("ix_applications_job_id", ["job_id"])
