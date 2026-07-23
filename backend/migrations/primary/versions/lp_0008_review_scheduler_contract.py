"""add scheduler contract metadata

Revision ID: lp_0008_review_contract
Revises: lp_0007_generation_jobs
"""

from alembic import op
import sqlalchemy as sa

revision = "lp_0008_review_contract"
down_revision = "lp_0007_generation_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wrong_questions", sa.Column("scheduler_version", sa.String(length=20), nullable=False, server_default="v1"))
    op.add_column("wrong_questions", sa.Column("difficulty_factor", sa.Integer(), nullable=False, server_default="100"))
    op.create_index("idx_wrong_question_due", "wrong_questions", ["user_id", "is_mastered", "next_review_at"])


def downgrade() -> None:
    op.drop_index("idx_wrong_question_due", table_name="wrong_questions")
    op.drop_column("wrong_questions", "difficulty_factor")
    op.drop_column("wrong_questions", "scheduler_version")
