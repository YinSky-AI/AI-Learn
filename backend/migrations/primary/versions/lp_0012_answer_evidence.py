"""persist bounded answer evidence

Revision ID: lp_0012_answer_evidence
Revises: lp_0011_adaptive_diagnosis
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "lp_0012_answer_evidence"
down_revision = "lp_0011_adaptive_diagnosis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("answers", "generated_practice_answers"):
        op.add_column(
            table,
            sa.Column(
                "solution_steps",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )
        op.add_column(
            table,
            sa.Column("student_confidence", sa.Integer(), nullable=True),
        )

    op.create_check_constraint(
        "ck_answer_student_confidence",
        "answers",
        "student_confidence IS NULL OR (student_confidence >= 1 AND student_confidence <= 5)",
    )
    op.create_check_constraint(
        "ck_generated_practice_answer_student_confidence",
        "generated_practice_answers",
        "student_confidence IS NULL OR (student_confidence >= 1 AND student_confidence <= 5)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_generated_practice_answer_student_confidence",
        "generated_practice_answers",
        type_="check",
    )
    op.drop_constraint(
        "ck_answer_student_confidence", "answers", type_="check"
    )
    for table in ("generated_practice_answers", "answers"):
        op.drop_column(table, "student_confidence")
        op.drop_column(table, "solution_steps")
