from datetime import date, datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import CheckConstraint

from app.models.adaptive_learning import AdaptationDecision, AnswerDiagnosis
from app.models.ai_generated import (
    GeneratedPracticeAnswer,
    GeneratedPracticeSubmission,
    GeneratedQuestion,
    GeneratedQuestionBatch,
    GenerationJob,
)
from app.models.content import AgeGroup, KnowledgeNode, Question, Subject
from app.models.learning import Answer, LearningSession
from app.models.user import User
from app.services.adaptive_question_service import (
    AdaptiveQuestionCandidate,
    get_next_for_decision,
    rank_candidates,
)


def test_candidate_ranking_prioritizes_misconception_skill_difficulty_then_exposure():
    now = datetime.now(timezone.utc)
    candidates = [
        AdaptiveQuestionCandidate("ordinary", uuid.uuid4(), False, True, True, None),
        AdaptiveQuestionCandidate("generated", uuid.uuid4(), True, False, True, now - timedelta(days=5)),
        AdaptiveQuestionCandidate("generated", uuid.uuid4(), True, True, False, None),
        AdaptiveQuestionCandidate("generated", uuid.uuid4(), True, True, True, now - timedelta(days=1)),
        AdaptiveQuestionCandidate("generated", uuid.uuid4(), True, True, True, now - timedelta(days=10)),
    ]

    ranked = rank_candidates(candidates)

    assert ranked[0] is candidates[4]
    assert ranked[1] is candidates[3]
    assert ranked[-1] is candidates[0]


def test_generation_job_accepts_exactly_one_standard_or_generated_source():
    table = GenerationJob.__table__
    assert "source_standard_question_id" in table.c
    assert table.c.source_question_id.nullable is True
    checks = " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "source_standard_question_id" in checks
    assert "source_question_id" in checks


async def _add_generated_decision(db, user_id, node, *, suffix: str):
    batch = GeneratedQuestionBatch(
        user_id=user_id,
        age_group_code="AGE_NEXT",
        subject_code="SUBJ_NEXT",
        course_topic="一元一次方程",
        difficulty_level=node.difficulty_level,
        question_types=["FILL_BLANK"],
        question_count=1,
        status="completed",
        prompt_version="test",
    )
    db.add(batch)
    await db.flush()
    source = GeneratedQuestion(
        batch_id=batch.id,
        user_id=user_id,
        knowledge_node_id=node.id,
        subject_code="SUBJ_NEXT",
        course_topic="一元一次方程",
        difficulty_level=node.difficulty_level,
        question_type="FILL_BLANK",
        question_body=f"{suffix}: 2x=8",
        options=None,
        correct_answer="x=4",
        explanation="内部解析",
        knowledge_tags=[node.code],
        source_prompt="internal",
        quality_status="failed",
    )
    db.add(source)
    await db.flush()
    submission = GeneratedPracticeSubmission(
        id=uuid.uuid4(),
        user_id=user_id,
        batch_id=batch.id,
        payload_fingerprint=suffix.ljust(64, "0")[:64],
        total_count=1,
        correct_count=0,
        accuracy_rate=0,
        time_spent_seconds=1,
        gamification={},
    )
    db.add(submission)
    await db.flush()
    answer = GeneratedPracticeAnswer(
        submission_id=submission.id,
        generated_question_id=source.id,
        position=0,
        user_answer="x=5",
        is_correct=False,
        correct_answer="x=4",
        explanation="内部解析",
        time_spent_seconds=1,
    )
    db.add(answer)
    await db.flush()
    diagnosis = AnswerDiagnosis(
        user_id=user_id,
        generated_answer_id=answer.id,
        status="diagnosed",
        knowledge_point_code=node.code,
        misconception_code="balance_violation",
        first_invalid_transition=0,
        evidence="不等价",
        confidence=0.9,
        source="rule",
        input_snapshot={},
    )
    db.add(diagnosis)
    await db.flush()
    decision = AdaptationDecision(
        user_id=user_id,
        diagnosis_id=diagnosis.id,
        action="practice_misconception",
        target_knowledge_node_id=node.id,
        target_misconception_code="balance_violation",
        reason_codes=["diagnosed_misconception"],
        policy_version="adaptive-equation-v1",
    )
    db.add(decision)
    await db.flush()
    return decision, batch, source


@pytest.mark.asyncio
async def test_next_question_selects_safe_reviewed_candidate_and_replays(db_session):
    user_id = uuid.uuid4()
    db_session.add_all(
        [
            Subject(code="SUBJ_NEXT", name="下一题", sort_order=0),
            AgeGroup(
                code="AGE_NEXT", name="下一题", min_age=12, max_age=15, theme_config={}
            ),
            User(
                id=user_id,
                nickname="下一题学生",
                email=f"next-{user_id}@example.test",
                password_hash="hash",
                birth_date=date(2012, 1, 1),
                age_group="AGE_NEXT",
            ),
        ]
    )
    await db_session.flush()
    target = KnowledgeNode(
        code="equation_equivalence",
        title="等式与等价变形",
        subject_code="SUBJ_NEXT",
        age_group_code="AGE_NEXT",
        difficulty_level="DIFF_EASY",
        content_type="TYPE_QUIZ",
        content_body="测试",
    )
    db_session.add(target)
    await db_session.flush()
    decision, batch, source = await _add_generated_decision(
        db_session, user_id, target, suffix="select"
    )
    source.quality_status = "passed"
    source.knowledge_tags = ["balance_violation"]
    ordinary = Question(
        id=uuid.uuid4(),
        knowledge_node_id=target.id,
        difficulty_level="DIFF_EASY",
        question_type="FILL_BLANK",
        question_body="3x=9",
        options=None,
        correct_answer="x=3",
        explanation="内部解析",
    )
    exact = GeneratedQuestion(
        batch_id=batch.id,
        user_id=user_id,
        knowledge_node_id=target.id,
        subject_code="SUBJ_NEXT",
        course_topic="一元一次方程",
        difficulty_level="DIFF_EASY",
        question_type="FILL_BLANK",
        question_body="4x=16",
        options=None,
        correct_answer="x=4",
        explanation="内部解析",
        knowledge_tags=[target.code],
        source_prompt="must-not-leak",
        quality_status="passed",
    )
    db_session.add_all([ordinary, exact])
    await db_session.flush()

    with pytest.raises(LookupError, match="不存在"):
        await get_next_for_decision(db_session, uuid.uuid4(), decision.id)
    first = await get_next_for_decision(db_session, user_id, decision.id)
    replay = await get_next_for_decision(db_session, user_id, decision.id)

    assert first == replay
    assert first["state"] == "ready"
    assert first["question"]["id"] == exact.id
    assert first["question"]["source"] == "generated"
    serialized = str(first)
    for secret in ("correct_answer", "内部解析", "must-not-leak"):
        assert secret not in serialized


@pytest.mark.asyncio
async def test_no_candidate_enqueues_one_recoverable_generation_job(db_session):
    user_id = uuid.uuid4()
    db_session.add_all(
        [
            Subject(code="SUBJ_NEXT", name="下一题", sort_order=0),
            AgeGroup(
                code="AGE_NEXT", name="下一题", min_age=12, max_age=15, theme_config={}
            ),
            User(
                id=user_id,
                nickname="生成学生",
                email=f"generate-{user_id}@example.test",
                password_hash="hash",
                birth_date=date(2012, 1, 1),
                age_group="AGE_NEXT",
            ),
        ]
    )
    await db_session.flush()
    target = KnowledgeNode(
        code="move_terms_sign",
        title="移项与符号变化",
        subject_code="SUBJ_NEXT",
        age_group_code="AGE_NEXT",
        difficulty_level="DIFF_MEDIUM",
        content_type="TYPE_QUIZ",
        content_body="测试",
    )
    db_session.add(target)
    await db_session.flush()
    decision, _batch, source = await _add_generated_decision(
        db_session, user_id, target, suffix="pending"
    )

    first = await get_next_for_decision(db_session, user_id, decision.id)
    replay = await get_next_for_decision(db_session, user_id, decision.id)

    assert first == replay
    assert first["state"] == "pending_generation"
    job = await db_session.get(GenerationJob, first["generation_job_id"])
    assert job.source_standard_question_id is None
    assert job.source_question_id == source.id
    assert job.target_knowledge_point_code == target.code
    assert job.target_misconception_code == decision.target_misconception_code
    assert job.policy_version == decision.policy_version
    assert isinstance(first["generation_job_id"], uuid.UUID)


@pytest.mark.asyncio
async def test_standard_answer_without_candidate_enqueues_one_generation_job(db_session):
    user_id = uuid.uuid4()
    db_session.add_all(
        [
            Subject(code="SUBJ_NEXT", name="下一题", sort_order=0),
            AgeGroup(
                code="AGE_NEXT", name="下一题", min_age=12, max_age=15, theme_config={}
            ),
            User(
                id=user_id,
                nickname="普通题学生",
                email=f"standard-next-{user_id}@example.test",
                password_hash="hash",
                birth_date=date(2012, 1, 1),
                age_group="AGE_NEXT",
            ),
        ]
    )
    await db_session.flush()
    target = KnowledgeNode(
        code="normalize_coefficient",
        title="系数化为 1",
        subject_code="SUBJ_NEXT",
        age_group_code="AGE_NEXT",
        difficulty_level="DIFF_MEDIUM",
        content_type="TYPE_QUIZ",
        content_body="测试",
    )
    db_session.add(target)
    await db_session.flush()
    question = Question(
        id=uuid.uuid4(),
        knowledge_node_id=target.id,
        difficulty_level="DIFF_MEDIUM",
        question_type="FILL_BLANK",
        question_body="2x=8",
        options=None,
        correct_answer="x=4",
        explanation="内部解析",
    )
    session = LearningSession(
        user_id=user_id,
        knowledge_node_id=target.id,
        difficulty_level="medium",
        status="in_progress",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add_all([question, session])
    await db_session.flush()
    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        user_answer="x=5",
        is_correct=False,
        time_spent_seconds=1,
    )
    db_session.add(answer)
    await db_session.flush()
    diagnosis = AnswerDiagnosis(
        user_id=user_id,
        standard_answer_id=answer.id,
        status="diagnosed",
        knowledge_point_code=target.code,
        misconception_code="coefficient_normalization_error",
        first_invalid_transition=0,
        evidence="不等价",
        confidence=0.9,
        source="rule",
        input_snapshot={},
    )
    db_session.add(diagnosis)
    await db_session.flush()
    decision = AdaptationDecision(
        user_id=user_id,
        diagnosis_id=diagnosis.id,
        action="practice_misconception",
        target_knowledge_node_id=target.id,
        target_misconception_code="coefficient_normalization_error",
        reason_codes=["diagnosed_misconception"],
        policy_version="adaptive-equation-v1",
    )
    db_session.add(decision)
    await db_session.flush()

    first = await get_next_for_decision(db_session, user_id, decision.id)
    replay = await get_next_for_decision(db_session, user_id, decision.id)

    assert first == replay
    assert first["state"] == "pending_generation"
    job = await db_session.get(GenerationJob, first["generation_job_id"])
    assert job.source_standard_question_id == question.id
    assert job.source_question_id is None
    assert job.target_knowledge_point_code == target.code
    assert job.target_misconception_code == decision.target_misconception_code
    assert job.policy_version == decision.policy_version
