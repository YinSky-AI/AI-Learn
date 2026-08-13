"""align the knowledge node code comment

Revision ID: lp_0016_node_code_comment
Revises: lp_0015_equation_knowledge_nodes
"""

import sqlalchemy as sa
from alembic import op


revision = "lp_0016_node_code_comment"
down_revision = "lp_0015_equation_knowledge_nodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "knowledge_nodes",
        "code",
        existing_type=sa.String(length=64),
        comment="稳定知识点编码",
    )


def downgrade() -> None:
    op.alter_column(
        "knowledge_nodes",
        "code",
        existing_type=sa.String(length=64),
        existing_comment="稳定知识点编码",
        comment=None,
    )
