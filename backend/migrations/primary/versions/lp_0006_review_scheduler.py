"""add deterministic wrong-question review scheduling

Revision ID: lp_0006_review_scheduler
Revises: lp_0005_generation_job
"""
from alembic import op
import sqlalchemy as sa

revision = "lp_0006_review_scheduler"
down_revision = "lp_0005_generation_job"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wrong_questions", sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE wrong_questions SET next_review_at = COALESCE(last_wrong_at, NOW()) WHERE next_review_at IS NULL")
    op.alter_column("wrong_questions", "next_review_at", nullable=False)


def downgrade() -> None:
    op.drop_column("wrong_questions", "next_review_at")
