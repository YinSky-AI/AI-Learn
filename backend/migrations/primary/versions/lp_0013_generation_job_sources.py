"""allow generated or standard sources for adaptive generation jobs

Revision ID: lp_0013_generation_job_sources
Revises: lp_0012_answer_evidence
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "lp_0013_generation_job_sources"
down_revision = "lp_0012_answer_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("generation_jobs", "source_question_id", nullable=True)
    op.add_column(
        "generation_jobs",
        sa.Column(
            "source_standard_question_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_generation_job_standard_source",
        "generation_jobs",
        "questions",
        ["source_standard_question_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_generation_job_exactly_one_source",
        "generation_jobs",
        "((source_question_id IS NOT NULL AND source_standard_question_id IS NULL) OR "
        "(source_question_id IS NULL AND source_standard_question_id IS NOT NULL))",
    )


def downgrade() -> None:
    # The old schema cannot represent standard-question sources. These queue
    # records are recoverable from their persisted adaptation decisions.
    op.execute("DELETE FROM generation_jobs WHERE source_question_id IS NULL")
    op.drop_constraint(
        "ck_generation_job_exactly_one_source", "generation_jobs", type_="check"
    )
    op.drop_constraint(
        "fk_generation_job_standard_source", "generation_jobs", type_="foreignkey"
    )
    op.drop_column("generation_jobs", "source_standard_question_id")
    op.alter_column("generation_jobs", "source_question_id", nullable=False)
