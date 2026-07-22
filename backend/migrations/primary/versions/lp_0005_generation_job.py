"""add generation job state fields

Revision ID: lp_0005_generation_job
Revises: lp_0004_account_principal
"""
from alembic import op
import sqlalchemy as sa

revision = "lp_0005_generation_job"
down_revision = "lp_0004_account_principal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_questions", sa.Column("generation_status", sa.String(length=20), nullable=False, server_default="succeeded"))
    op.add_column("generated_questions", sa.Column("generation_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("generated_questions", sa.Column("generation_max_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("generated_questions", sa.Column("generation_failure_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_questions", "generation_failure_reason")
    op.drop_column("generated_questions", "generation_max_attempts")
    op.drop_column("generated_questions", "generation_attempts")
    op.drop_column("generated_questions", "generation_status")
