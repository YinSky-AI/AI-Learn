"""persist adaptive equation diagnosis state

Revision ID: lp_0011_adaptive_diagnosis
Revises: lp_0010_practice_history
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "lp_0011_adaptive_diagnosis"
down_revision = "lp_0010_practice_history"
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


def _exactly_one_answer(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "((standard_answer_id IS NOT NULL AND generated_answer_id IS NULL) OR "
        "(standard_answer_id IS NULL AND generated_answer_id IS NOT NULL))",
        name=name,
    )


def upgrade() -> None:
    op.add_column("knowledge_nodes", sa.Column("code", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE knowledge_nodes SET code = 'legacy-' || "
        "substring(replace(id::text, '-', '') from 1 for 12) WHERE code IS NULL"
    )
    op.alter_column("knowledge_nodes", "code", nullable=False)
    op.create_unique_constraint("uq_knowledge_nodes_code", "knowledge_nodes", ["code"])
    op.alter_column(
        "knowledge_nodes",
        "code",
        server_default=sa.text(
            "('legacy-' || substring(replace(uuid_generate_v4()::text, '-', '') from 1 for 12))"
        ),
    )

    op.create_table(
        "diagnosis_jobs",
        *_base_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("generated_answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_practice_answers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=100), nullable=True),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _exactly_one_answer("ck_diagnosis_job_exactly_one_answer"),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="ck_diagnosis_job_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_diagnosis_job_attempts_nonnegative"),
        sa.CheckConstraint("max_attempts > 0", name="ck_diagnosis_job_max_attempts_positive"),
        sa.CheckConstraint("attempts <= max_attempts", name="ck_diagnosis_job_attempts_bounded"),
        sa.UniqueConstraint("standard_answer_id", name="uq_diagnosis_job_standard_answer"),
        sa.UniqueConstraint("generated_answer_id", name="uq_diagnosis_job_generated_answer"),
    )
    op.create_index("idx_diagnosis_job_status_lease_created", "diagnosis_jobs", ["status", "lease_expires_at", "created_at"])
    op.create_index("idx_diagnosis_job_user_created", "diagnosis_jobs", ["user_id", "created_at"])

    op.create_table(
        "answer_diagnoses",
        *_base_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("answers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("generated_answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_practice_answers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("knowledge_point_code", sa.String(length=64), sa.ForeignKey("knowledge_nodes.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("misconception_code", sa.String(length=64), nullable=True),
        sa.Column("first_invalid_transition", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(), nullable=True),
        _exactly_one_answer("ck_answer_diagnosis_exactly_one_answer"),
        sa.CheckConstraint("status IN ('diagnosed', 'insufficient_evidence', 'not_required')", name="ck_answer_diagnosis_status"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_answer_diagnosis_confidence"),
        sa.CheckConstraint("first_invalid_transition IS NULL OR first_invalid_transition >= 0", name="ck_answer_diagnosis_transition_nonnegative"),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_answer_diagnosis_latency_nonnegative"),
        sa.UniqueConstraint("standard_answer_id", name="uq_answer_diagnosis_standard_answer"),
        sa.UniqueConstraint("generated_answer_id", name="uq_answer_diagnosis_generated_answer"),
    )
    op.create_index("idx_answer_diagnosis_user_created", "answer_diagnoses", ["user_id", "created_at"])
    op.create_index("idx_answer_diagnosis_knowledge_misconception", "answer_diagnoses", ["knowledge_point_code", "misconception_code"])

    op.create_table(
        "knowledge_mastery_states",
        *_base_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("p_known", sa.Numeric(5, 4), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_answer_ref", sa.String(length=100), nullable=True),
        sa.CheckConstraint("p_known >= 0 AND p_known <= 1", name="ck_mastery_p_known"),
        sa.CheckConstraint("observation_count >= 0", name="ck_mastery_observation_nonnegative"),
        sa.UniqueConstraint("user_id", "knowledge_node_id", "model_version", name="uq_mastery_user_node_version"),
    )
    op.create_index("idx_mastery_user_updated", "knowledge_mastery_states", ["user_id", "updated_at"])

    op.execute(
        """
        INSERT INTO knowledge_mastery_states (
            id, user_id, knowledge_node_id, p_known, model_version,
            observation_count, created_at, updated_at
        )
        SELECT
            uuid_generate_v4(), u.id, kn.id,
            LEAST(1, GREATEST(0, CASE
                WHEN jsonb_typeof(entry.value -> 'level') = 'number'
                THEN (entry.value ->> 'level')::numeric
                ELSE 0.35
            END)),
            'bkt-equation-v1',
            GREATEST(0, CASE
                WHEN jsonb_typeof(entry.value -> 'total') = 'number'
                THEN (entry.value ->> 'total')::integer
                ELSE 0
            END),
            NOW(), NOW()
        FROM users AS u
        CROSS JOIN LATERAL jsonb_each(CASE
            WHEN jsonb_typeof(u.behavior_profile -> 'knowledge_mastery') = 'object'
            THEN u.behavior_profile -> 'knowledge_mastery'
            ELSE '{}'::jsonb
        END) AS entry(key, value)
        JOIN LATERAL (
            SELECT exact_node.id
            FROM knowledge_nodes AS exact_node
            WHERE exact_node.code = entry.key
            UNION ALL
            SELECT titled_node.id
            FROM knowledge_nodes AS titled_node
            WHERE titled_node.title = entry.key
              AND NOT EXISTS (
                  SELECT 1 FROM knowledge_nodes AS exact_node
                  WHERE exact_node.code = entry.key
              )
              AND (
                  SELECT COUNT(*) FROM knowledge_nodes AS title_count
                  WHERE title_count.title = entry.key
              ) = 1
            LIMIT 1
        ) AS kn ON TRUE
        ON CONFLICT (user_id, knowledge_node_id, model_version) DO NOTHING
        """
    )

    op.create_table(
        "adaptation_decisions",
        *_base_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("answer_diagnoses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("target_knowledge_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_nodes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_misconception_code", sa.String(length=64), nullable=True),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("selected_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("generated_question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_questions.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("diagnosis_id", name="uq_adaptation_decision_diagnosis"),
        sa.CheckConstraint(
            "action IN ('ask_diagnostic_question', 'review_prerequisite', "
            "'practice_misconception', 'practice_same_skill', 'increase_difficulty')",
            name="ck_adaptation_decision_action",
        ),
    )
    op.create_index("idx_adaptation_decision_user_created", "adaptation_decisions", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_adaptation_decision_user_created", table_name="adaptation_decisions")
    op.drop_table("adaptation_decisions")
    op.drop_index("idx_mastery_user_updated", table_name="knowledge_mastery_states")
    op.drop_table("knowledge_mastery_states")
    op.drop_index("idx_answer_diagnosis_knowledge_misconception", table_name="answer_diagnoses")
    op.drop_index("idx_answer_diagnosis_user_created", table_name="answer_diagnoses")
    op.drop_table("answer_diagnoses")
    op.drop_index("idx_diagnosis_job_user_created", table_name="diagnosis_jobs")
    op.drop_index("idx_diagnosis_job_status_lease_created", table_name="diagnosis_jobs")
    op.drop_table("diagnosis_jobs")
    op.drop_constraint("uq_knowledge_nodes_code", "knowledge_nodes", type_="unique")
    op.alter_column("knowledge_nodes", "code", server_default=None)
    op.drop_column("knowledge_nodes", "code")
