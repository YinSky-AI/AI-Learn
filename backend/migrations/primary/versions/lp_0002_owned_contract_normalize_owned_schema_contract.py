"""normalize owned schema contract

Revision ID: lp_0002_owned_contract
Revises: lp_0001_legacy_baseline
Create Date: 2026-07-22 06:23:15.464520
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'lp_0002_owned_contract'
down_revision: Union[str, None] = 'lp_0001_legacy_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    orphan_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM lessons l "
            "LEFT JOIN knowledge_nodes k ON k.id = l.knowledge_node_id "
            "WHERE l.knowledge_node_id IS NOT NULL AND k.id IS NULL"
        )
    ).scalar_one()
    if orphan_count:
        raise RuntimeError("Schema 迁移已停止：课时存在无效知识点关联")

    op.execute(
        "ALTER INDEX idx_lesson_knowledge_node "
        "RENAME TO ix_lessons_knowledge_node_id"
    )
    op.create_foreign_key(
        "fk_lessons_knowledge_node_id",
        "lessons",
        "knowledge_nodes",
        ["knowledge_node_id"],
        ["id"],
        ondelete="SET NULL",
        postgresql_not_valid=True,
    )
    op.execute(
        "ALTER TABLE lessons VALIDATE CONSTRAINT fk_lessons_knowledge_node_id"
    )
    op.execute(
        "ALTER TABLE user_achievements "
        "ADD CONSTRAINT uq_user_achievement_user_achievement "
        "UNIQUE USING INDEX uq_user_achievement_user_achievement"
    )


def downgrade() -> None:
    op.drop_constraint('uq_user_achievement_user_achievement', 'user_achievements', type_='unique')
    op.create_index('uq_user_achievement_user_achievement', 'user_achievements', ['user_id', 'achievement_id'], unique=True)
    op.drop_constraint('fk_lessons_knowledge_node_id', 'lessons', type_='foreignkey')
    op.execute(
        "ALTER INDEX ix_lessons_knowledge_node_id "
        "RENAME TO idx_lesson_knowledge_node"
    )
