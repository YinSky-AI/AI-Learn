from sqlalchemy.dialects.postgresql import JSONB

import app.models as models_module
from app.models.adaptive_learning import (
    AdaptationDecision,
    AnswerDiagnosis,
    DiagnosisJob,
    KnowledgeMasteryState,
)
from app.models.content import KnowledgeNode


def constraint_sql(table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    )


def unique_column_sets(table) -> set[frozenset[str]]:
    return {
        frozenset(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }


def test_adaptive_models_publish_the_documented_tables():
    """Renaming or failing to register an adaptive table must make this test fail."""

    assert DiagnosisJob.__tablename__ == "diagnosis_jobs"
    assert AnswerDiagnosis.__tablename__ == "answer_diagnoses"
    assert KnowledgeMasteryState.__tablename__ == "knowledge_mastery_states"
    assert AdaptationDecision.__tablename__ == "adaptation_decisions"
    assert {
        "DiagnosisJob",
        "AnswerDiagnosis",
        "KnowledgeMasteryState",
        "AdaptationDecision",
    } <= set(models_module.__all__)


def test_job_and_diagnosis_require_exactly_one_answer_reference():
    """Allowing zero or two answer owners must make this test fail."""

    for model in (DiagnosisJob, AnswerDiagnosis):
        table = model.__table__
        sql = constraint_sql(table)
        assert "standard_answer_id IS NOT NULL" in sql
        assert "generated_answer_id IS NOT NULL" in sql
        assert "standard_answer_id IS NULL" in sql
        assert "generated_answer_id IS NULL" in sql
        uniques = unique_column_sets(table)
        assert frozenset({"standard_answer_id"}) in uniques
        assert frozenset({"generated_answer_id"}) in uniques
        assert (
            next(iter(table.c.standard_answer_id.foreign_keys)).target_fullname
            == "answers.id"
        )
        assert (
            next(iter(table.c.generated_answer_id.foreign_keys)).target_fullname
            == "generated_practice_answers.id"
        )


def test_job_lease_and_status_contract_is_queryable_and_bounded():
    """Dropping queue bounds or the claim index must make this test fail."""

    table = DiagnosisJob.__table__
    assert {
        "status",
        "attempts",
        "max_attempts",
        "lease_owner",
        "lease_expires_at",
        "failure_reason",
        "input_snapshot",
    } <= set(table.c.keys())
    assert isinstance(table.c.input_snapshot.type, JSONB)
    assert "queued" in constraint_sql(table)
    assert "attempts >= 0" in constraint_sql(table)
    assert any(
        tuple(column.name for column in index.columns)
        == ("status", "lease_expires_at", "created_at")
        for index in table.indexes
    )


def test_diagnosis_uses_typed_query_fields_and_bounded_json_only():
    """Moving filter or metric fields into arbitrary JSON must make this fail."""

    table = AnswerDiagnosis.__table__
    assert {
        "status",
        "knowledge_point_code",
        "misconception_code",
        "first_invalid_transition",
        "confidence",
        "source",
        "prompt_version",
        "model_name",
        "latency_ms",
    } <= set(table.c.keys())
    assert isinstance(table.c.input_snapshot.type, JSONB)
    assert isinstance(table.c.token_usage.type, JSONB)
    assert (
        next(iter(table.c.knowledge_point_code.foreign_keys)).target_fullname
        == "knowledge_nodes.code"
    )
    assert "confidence >= 0" in constraint_sql(table)
    assert "confidence <= 1" in constraint_sql(table)


def test_mastery_and_decision_enforce_once_per_versioned_event():
    """Dropping mastery identity or one-decision-per-diagnosis must make this fail."""

    mastery = KnowledgeMasteryState.__table__
    decision = AdaptationDecision.__table__
    assert frozenset({"user_id", "knowledge_node_id", "model_version"}) in unique_column_sets(mastery)
    assert frozenset({"diagnosis_id"}) in unique_column_sets(decision)
    assert "p_known >= 0" in constraint_sql(mastery)
    assert "p_known <= 1" in constraint_sql(mastery)
    assert "observation_count >= 0" in constraint_sql(mastery)
    assert isinstance(decision.c.reason_codes.type, JSONB)


def test_knowledge_node_code_is_the_unique_non_null_runtime_key():
    """Leaving runtime knowledge identity tied to mutable titles must make this fail."""

    code = KnowledgeNode.__table__.c.code
    assert code.nullable is False
    assert code.unique is True
