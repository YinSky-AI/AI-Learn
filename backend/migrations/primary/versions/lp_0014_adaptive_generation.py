"""persist adaptive constraints for generated variants

Revision ID: lp_0014_adaptive_generation
Revises: lp_0013_generation_job_sources
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "lp_0014_adaptive_generation"
down_revision = "lp_0013_generation_job_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("target_knowledge_point_code", sa.String(64), nullable=True))
    op.add_column("generation_jobs", sa.Column("target_misconception_code", sa.String(64), nullable=True))
    op.add_column("generation_jobs", sa.Column("policy_version", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_generation_job_target_knowledge_code",
        "generation_jobs",
        "knowledge_nodes",
        ["target_knowledge_point_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.add_column("generated_questions", sa.Column("target_knowledge_point_code", sa.String(64), nullable=True))
    op.add_column("generated_questions", sa.Column("target_misconception_code", sa.String(64), nullable=True))
    op.add_column("generated_questions", sa.Column("generation_policy_version", sa.String(64), nullable=True))
    op.add_column("generated_questions", sa.Column("parent_standard_question_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_generated_question_target_knowledge_code",
        "generated_questions",
        "knowledge_nodes",
        ["target_knowledge_point_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_generated_question_standard_parent",
        "generated_questions",
        "questions",
        ["parent_standard_question_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_generated_question_standard_parent", "generated_questions", type_="foreignkey")
    op.drop_constraint("fk_generated_question_target_knowledge_code", "generated_questions", type_="foreignkey")
    op.drop_column("generated_questions", "parent_standard_question_id")
    op.drop_column("generated_questions", "generation_policy_version")
    op.drop_column("generated_questions", "target_misconception_code")
    op.drop_column("generated_questions", "target_knowledge_point_code")
    op.drop_constraint("fk_generation_job_target_knowledge_code", "generation_jobs", type_="foreignkey")
    op.drop_column("generation_jobs", "policy_version")
    op.drop_column("generation_jobs", "target_misconception_code")
    op.drop_column("generation_jobs", "target_knowledge_point_code")
