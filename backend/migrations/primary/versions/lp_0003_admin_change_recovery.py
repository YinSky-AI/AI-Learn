"""add recoverable administrative changes

Revision ID: lp_0003_admin_recovery
Revises: lp_0002_owned_contract
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "lp_0003_admin_recovery"
down_revision = "lp_0002_owned_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("lessons", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_courses_deleted_at", "courses", ["deleted_at"])
    op.create_index("ix_lessons_deleted_at", "lessons", ["deleted_at"])
    op.create_table(
        "admin_change_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("before_summary", postgresql.JSONB(), nullable=False),
        sa.Column("after_summary", postgresql.JSONB(), nullable=False),
        sa.Column("impact_scope", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_admin_change_entity", "admin_change_audits", ["entity_type", "entity_id", "created_at"])


def downgrade() -> None:
    op.drop_table("admin_change_audits")
    op.drop_index("ix_lessons_deleted_at", table_name="lessons")
    op.drop_index("ix_courses_deleted_at", table_name="courses")
    op.drop_column("lessons", "deleted_at")
    op.drop_column("courses", "deleted_at")
