"""add recoverable question administration

Revision ID: catalog_0002_admin_recovery
Revises: catalog_0001_baseline
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "catalog_0002_admin_recovery"
down_revision = "catalog_0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_questions_deleted_at", "questions", ["deleted_at"])
    op.create_table(
        "admin_change_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
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
    op.create_index("ix_catalog_admin_change_entity", "admin_change_audits", ["entity_type", "entity_id", "created_at"])


def downgrade() -> None:
    op.drop_table("admin_change_audits")
    op.drop_index("ix_questions_deleted_at", table_name="questions")
    op.drop_column("questions", "deleted_at")
