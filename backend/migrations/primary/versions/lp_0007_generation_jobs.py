"""add durable generation jobs

Revision ID: lp_0007_generation_jobs
Revises: lp_0006_review_scheduler
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "lp_0007_generation_jobs"
down_revision = "lp_0006_review_scheduler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_difficulty", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("result_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_questions.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("idx_generation_job_status_lease", "generation_jobs", ["status", "lease_expires_at"])
    op.create_index("idx_generation_job_user_created", "generation_jobs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_generation_job_user_created", table_name="generation_jobs")
    op.drop_index("idx_generation_job_status_lease", table_name="generation_jobs")
    op.drop_table("generation_jobs")
