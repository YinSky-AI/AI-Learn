"""add generated and wrong-practice idempotency contracts

Revision ID: lp_0009_practice_contract
Revises: lp_0008_review_contract
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "lp_0009_practice_contract"
down_revision = "lp_0008_review_contract"
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "generated_practice_submissions",
        *_base_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_question_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("accuracy_rate", sa.Float(), nullable=False),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("gamification", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("total_count >= 0", name="ck_generated_practice_submission_total_nonnegative"),
        sa.CheckConstraint("correct_count >= 0", name="ck_generated_practice_submission_correct_nonnegative"),
        sa.CheckConstraint("time_spent_seconds >= 0", name="ck_generated_practice_submission_time_nonnegative"),
    )
    op.create_index("idx_generated_practice_submission_user_created", "generated_practice_submissions", ["user_id", "created_at"])
    op.create_index("idx_generated_practice_submission_batch_created", "generated_practice_submissions", ["batch_id", "created_at"])

    op.create_table(
        "generated_practice_answers",
        *_base_columns(),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_practice_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("submission_id", "generated_question_id", name="uq_generated_practice_answer_submission_question"),
        sa.CheckConstraint("position >= 0", name="ck_generated_practice_answer_position_nonnegative"),
        sa.CheckConstraint("time_spent_seconds >= 0", name="ck_generated_practice_answer_time_nonnegative"),
    )
    op.create_index("idx_generated_practice_answer_question", "generated_practice_answers", ["generated_question_id"])

    op.create_table(
        "generated_practice_reward_events",
        *_base_columns(),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_practice_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_practice_answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_practice_answers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("base_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak_bonus", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("correct_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_achievements", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.UniqueConstraint("user_id", "generated_question_id", name="uq_generated_practice_reward_user_question"),
    )
    op.create_index("idx_generated_practice_reward_user_created", "generated_practice_reward_events", ["user_id", "created_at"])

    op.create_table(
        "wrong_practice_attempts",
        *_base_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("idx_wrong_practice_attempt_user_question", "wrong_practice_attempts", ["user_id", "question_id"])


def downgrade() -> None:
    op.drop_index("idx_wrong_practice_attempt_user_question", table_name="wrong_practice_attempts")
    op.drop_table("wrong_practice_attempts")
    op.drop_index("idx_generated_practice_reward_user_created", table_name="generated_practice_reward_events")
    op.drop_table("generated_practice_reward_events")
    op.drop_index("idx_generated_practice_answer_question", table_name="generated_practice_answers")
    op.drop_table("generated_practice_answers")
    op.drop_index("idx_generated_practice_submission_batch_created", table_name="generated_practice_submissions")
    op.drop_index("idx_generated_practice_submission_user_created", table_name="generated_practice_submissions")
    op.drop_table("generated_practice_submissions")
