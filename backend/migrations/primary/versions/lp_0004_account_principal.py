"""add account principal credential versioning

Revision ID: lp_0004_account_principal
Revises: lp_0003_admin_recovery
"""
from alembic import op
import sqlalchemy as sa

revision = "lp_0004_account_principal"
down_revision = "lp_0003_admin_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("credential_version", sa.Integer(), nullable=False, server_default=sa.text("1"), comment="凭证版本，用于全局作废"))
    op.add_column("users", sa.Column("credentials_revoked_at", sa.DateTime(timezone=True), nullable=True, comment="最近一次凭证撤销时间"))


def downgrade() -> None:
    op.drop_column("users", "credentials_revoked_at")
    op.drop_column("users", "credential_version")
