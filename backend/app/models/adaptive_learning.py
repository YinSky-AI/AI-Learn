"""Persistent diagnosis, mastery, and adaptation state."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import BaseModel
from app.models import Base


_EXACTLY_ONE_ANSWER = """(
    standard_answer_id IS NOT NULL AND generated_answer_id IS NULL
) OR (
    standard_answer_id IS NULL AND generated_answer_id IS NOT NULL
)"""


class DiagnosisJob(BaseModel, Base):
    __tablename__ = "diagnosis_jobs"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    standard_answer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=True,
    )
    generated_answer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generated_practice_answers.id", ondelete="CASCADE"),
        nullable=True,
    )
    status = Column(String(20), nullable=False, default="queued", server_default="queued")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=3, server_default="3")
    lease_owner = Column(String(128), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(String(100), nullable=True)
    input_snapshot = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        CheckConstraint(_EXACTLY_ONE_ANSWER, name="ck_diagnosis_job_exactly_one_answer"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_diagnosis_job_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_diagnosis_job_attempts_nonnegative"),
        CheckConstraint("max_attempts > 0", name="ck_diagnosis_job_max_attempts_positive"),
        CheckConstraint("attempts <= max_attempts", name="ck_diagnosis_job_attempts_bounded"),
        UniqueConstraint("standard_answer_id", name="uq_diagnosis_job_standard_answer"),
        UniqueConstraint("generated_answer_id", name="uq_diagnosis_job_generated_answer"),
        Index("idx_diagnosis_job_status_lease_created", "status", "lease_expires_at", "created_at"),
        Index("idx_diagnosis_job_user_created", "user_id", "created_at"),
    )


class AnswerDiagnosis(BaseModel, Base):
    __tablename__ = "answer_diagnoses"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    standard_answer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=True,
    )
    generated_answer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generated_practice_answers.id", ondelete="CASCADE"),
        nullable=True,
    )
    status = Column(String(30), nullable=False)
    knowledge_point_code = Column(
        String(64),
        ForeignKey("knowledge_nodes.code", ondelete="RESTRICT"),
        nullable=False,
    )
    misconception_code = Column(String(64), nullable=True)
    first_invalid_transition = Column(Integer, nullable=True)
    evidence = Column(Text, nullable=False)
    confidence = Column(Numeric(5, 4), nullable=False)
    source = Column(String(20), nullable=False)
    input_snapshot = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    prompt_version = Column(String(64), nullable=True)
    model_name = Column(String(128), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    token_usage = Column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(_EXACTLY_ONE_ANSWER, name="ck_answer_diagnosis_exactly_one_answer"),
        CheckConstraint(
            "status IN ('diagnosed', 'insufficient_evidence', 'not_required')",
            name="ck_answer_diagnosis_status",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_answer_diagnosis_confidence"),
        CheckConstraint(
            "first_invalid_transition IS NULL OR first_invalid_transition >= 0",
            name="ck_answer_diagnosis_transition_nonnegative",
        ),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_answer_diagnosis_latency_nonnegative"),
        UniqueConstraint("standard_answer_id", name="uq_answer_diagnosis_standard_answer"),
        UniqueConstraint("generated_answer_id", name="uq_answer_diagnosis_generated_answer"),
        Index("idx_answer_diagnosis_user_created", "user_id", "created_at"),
        Index("idx_answer_diagnosis_knowledge_misconception", "knowledge_point_code", "misconception_code"),
    )


class KnowledgeMasteryState(BaseModel, Base):
    __tablename__ = "knowledge_mastery_states"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    p_known = Column(Numeric(5, 4), nullable=False)
    model_version = Column(String(64), nullable=False)
    observation_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_answer_ref = Column(String(100), nullable=True)

    __table_args__ = (
        CheckConstraint("p_known >= 0 AND p_known <= 1", name="ck_mastery_p_known"),
        CheckConstraint("observation_count >= 0", name="ck_mastery_observation_nonnegative"),
        UniqueConstraint(
            "user_id",
            "knowledge_node_id",
            "model_version",
            name="uq_mastery_user_node_version",
        ),
        Index("idx_mastery_user_updated", "user_id", "updated_at"),
    )


class AdaptationDecision(BaseModel, Base):
    __tablename__ = "adaptation_decisions"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    diagnosis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("answer_diagnoses.id", ondelete="CASCADE"),
        nullable=False,
    )
    action = Column(String(40), nullable=False)
    target_knowledge_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_nodes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_misconception_code = Column(String(64), nullable=True)
    reason_codes = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    policy_version = Column(String(64), nullable=False)
    selected_question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    generated_question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generated_questions.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("diagnosis_id", name="uq_adaptation_decision_diagnosis"),
        CheckConstraint(
            "action IN ('ask_diagnostic_question', 'review_prerequisite', "
            "'practice_misconception', 'practice_same_skill', 'increase_difficulty')",
            name="ck_adaptation_decision_action",
        ),
        Index("idx_adaptation_decision_user_created", "user_id", "created_at"),
    )
