"""preserve practice submission history across question deletion

Revision ID: lp_0010_practice_history
Revises: lp_0009_practice_contract
"""

from alembic import op


revision = "lp_0010_practice_history"
down_revision = "lp_0009_practice_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("generated_practice_answers_generated_question_id_fkey", "generated_practice_answers", type_="foreignkey")
    op.drop_constraint("generated_practice_reward_events_generated_question_id_fkey", "generated_practice_reward_events", type_="foreignkey")
    op.drop_constraint("wrong_practice_attempts_question_id_fkey", "wrong_practice_attempts", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        "generated_practice_answers_generated_question_id_fkey",
        "generated_practice_answers",
        "generated_questions",
        ["generated_question_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "generated_practice_reward_events_generated_question_id_fkey",
        "generated_practice_reward_events",
        "generated_questions",
        ["generated_question_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "wrong_practice_attempts_question_id_fkey",
        "wrong_practice_attempts",
        "questions",
        ["question_id"],
        ["id"],
        ondelete="CASCADE",
    )
