from datetime import date, datetime, timezone
import uuid

import pytest
from fastapi import HTTPException

from app.api.v1.adaptive import get_diagnosis_job
from app.models.adaptive_learning import (
    AdaptationDecision,
    AnswerDiagnosis,
    DiagnosisJob,
    KnowledgeMasteryState,
)
from app.models.content import AgeGroup, KnowledgeNode, Question, Subject
from app.models.learning import Answer, LearningSession
from app.models.user import User
from app.core.security import create_access_token


async def _diagnosis_fixture(db):
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    node_id, question_id, session_id, answer_id = (uuid.uuid4() for _ in range(4))
    db.add_all(
        [
            Subject(code="SUBJ_ADAPT", name="自适应数学", sort_order=0),
            AgeGroup(
                code="AGE_ADAPT",
                name="自适应测试",
                min_age=12,
                max_age=15,
                theme_config={},
            ),
            User(
                id=owner_id,
                nickname="学生",
                email=f"adaptive-{owner_id}@example.test",
                password_hash="hash",
                birth_date=date(2012, 1, 1),
                age_group="AGE_ADAPT",
            ),
            User(
                id=other_id,
                nickname="他人",
                email=f"adaptive-{other_id}@example.test",
                password_hash="hash",
                birth_date=date(2012, 1, 1),
                age_group="AGE_ADAPT",
            ),
            KnowledgeNode(
                id=node_id,
                code="equation_equivalence",
                title="等式与等价变形",
                subject_code="SUBJ_ADAPT",
                age_group_code="AGE_ADAPT",
                difficulty_level="DIFF_EASY",
                content_type="TYPE_QUIZ",
                content_body="测试",
            ),
        ]
    )
    await db.flush()
    db.add_all(
        [
            Question(
                id=question_id,
                knowledge_node_id=node_id,
                difficulty_level="DIFF_EASY",
                question_type="FILL_BLANK",
                question_body="2x=8",
                options=None,
                correct_answer="x=4",
                explanation="不应由诊断接口返回",
            ),
            LearningSession(
                id=session_id,
                user_id=owner_id,
                knowledge_node_id=node_id,
                difficulty_level="DIFF_EASY",
                status="in_progress",
                started_at=datetime.now(timezone.utc),
            ),
        ]
    )
    await db.flush()
    answer = Answer(
        id=answer_id,
        session_id=session_id,
        question_id=question_id,
        user_answer="x=5",
        is_correct=False,
        time_spent_seconds=3,
        solution_steps=["2x=8", "x=5"],
    )
    db.add(answer)
    await db.flush()
    job = DiagnosisJob(
        user_id=owner_id,
        standard_answer_id=answer_id,
        status="queued",
        input_snapshot={},
    )
    db.add(job)
    await db.flush()
    return owner_id, other_id, node_id, answer_id, job


@pytest.mark.asyncio
async def test_diagnosis_endpoint_is_owner_scoped_and_returns_stable_states(db_session):
    owner_id, other_id, node_id, answer_id, job = await _diagnosis_fixture(db_session)

    pending = await get_diagnosis_job(job.id, owner_id, db_session)
    assert pending["data"] == {"job_id": job.id, "state": "pending"}

    for requester, missing_id in ((other_id, job.id), (owner_id, uuid.uuid4())):
        with pytest.raises(HTTPException) as exc:
            await get_diagnosis_job(missing_id, requester, db_session)
        assert exc.value.status_code == 404

    job.status = "failed"
    job.failure_reason = "provider-secret-payload"
    await db_session.flush()
    failed = await get_diagnosis_job(job.id, owner_id, db_session)
    assert failed["data"] == {
        "job_id": job.id,
        "state": "failed",
        "retryable": False,
        "message": "诊断暂时未完成，请稍后重新作答",
    }
    assert "provider-secret-payload" not in str(failed)

    diagnosis = AnswerDiagnosis(
        user_id=owner_id,
        standard_answer_id=answer_id,
        status="diagnosed",
        knowledge_point_code="equation_equivalence",
        misconception_code="balance_violation",
        first_invalid_transition=0,
        evidence="从步骤 1 到步骤 2 不等价",
        confidence=0.9,
        source="rule",
        input_snapshot={
            "mastery_before": "0.3500",
            "mastery_after": "0.2036",
            "mastery_model_version": "bkt-equation-v1",
            "raw_model_output": "不得返回",
        },
        prompt_version="internal-prompt",
        model_name="internal-model",
        token_usage={"total_tokens": 99},
    )
    db_session.add(diagnosis)
    await db_session.flush()
    db_session.add_all(
        [
            KnowledgeMasteryState(
                user_id=owner_id,
                knowledge_node_id=node_id,
                p_known=0.2036,
                model_version="bkt-equation-v1",
                observation_count=1,
            ),
            AdaptationDecision(
                user_id=owner_id,
                diagnosis_id=diagnosis.id,
                action="practice_misconception",
                target_knowledge_node_id=node_id,
                target_misconception_code="balance_violation",
                reason_codes=["diagnosed_misconception"],
                policy_version="adaptive-equation-v1",
            ),
        ]
    )
    job.status = "succeeded"
    await db_session.flush()

    succeeded = await get_diagnosis_job(job.id, owner_id, db_session)
    data = succeeded["data"]
    assert data["state"] == "succeeded"
    assert data["diagnosis"]["first_invalid_step"] == 2
    assert data["mastery"] == {
        "before": 0.35,
        "after": 0.2036,
        "model_version": "bkt-equation-v1",
    }
    assert data["next_action"]["action"] == "practice_misconception"
    serialized = str(data)
    for secret in ("internal-prompt", "internal-model", "raw_model_output", "total_tokens"):
        assert secret not in serialized


@pytest.mark.asyncio
async def test_diagnosis_route_uses_authenticated_owner_and_public_schema(
    client, db_session
):
    owner_id, other_id, _node_id, _answer_id, job = await _diagnosis_fixture(
        db_session
    )

    owner = await client.get(
        f"/api/v1/adaptive/diagnoses/jobs/{job.id}",
        headers={"Authorization": f"Bearer {create_access_token(owner_id)}"},
    )
    other = await client.get(
        f"/api/v1/adaptive/diagnoses/jobs/{job.id}",
        headers={"Authorization": f"Bearer {create_access_token(other_id)}"},
    )

    assert owner.status_code == 200
    assert owner.json()["data"] == {"job_id": str(job.id), "state": "pending"}
    assert other.status_code == 404
