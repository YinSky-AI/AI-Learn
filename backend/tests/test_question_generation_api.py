import asyncio
import hashlib
import json
import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.tools.question_memory_tool import QuestionMemoryTool
from app.api.v1 import questions as questions_api
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.security import create_access_token
from app.main import app
from app.models.ai_generated import (
    GeneratedPracticeAnswer,
    GeneratedPracticeRewardEvent,
    GeneratedPracticeSubmission,
    GeneratedQuestion,
    GeneratedQuestionBatch,
    QuestionQualityCheck,
)
from app.models import Base
from app.models.user import User
from app.schemas.question import (
    BatchResponse,
    GeneratedPracticeSubmitRequest,
    GeneratedQuestionResponse,
)
from app.services.behavior_service import BehaviorService


REQUEST_PAYLOAD = {
    "age_group_code": "10-12",
    "subject_code": "数学",
    "course_topic": "分数加法",
    "difficulty_level": "medium",
    "question_types": ["choice"],
    "question_count": 1,
    "learning_goal": "掌握同分母分数加法",
}

GENERATED_QUESTION = {
    "question_type": "choice",
    "question_body": "小明吃了八分之三块蛋糕，又吃了八分之二块，一共吃了多少？",
    "options": [
        {
            "key": "A",
            "value": "八分之五",
            "is_correct": True,
            "metadata": {
                "correct_answer": "A",
                "analysis": "同分母直接相加",
                "safe_hint": "先观察分母",
            },
        },
        {"key": "B", "value": "八分之六"},
    ],
    "correct_answer": "A",
    "explanation": "同分母分数相加，分母不变，分子相加。",
    "tags": ["同分母分数加法"],
    "difficulty": "medium",
}


def test_generated_question_difficulty_columns_fit_platform_codes():
    """ORM 字段必须能保存内部标准难度编码（例如 DIFF_MEDIUM）。"""
    required_length = len("DIFF_MEDIUM")

    assert GeneratedQuestionBatch.__table__.c.difficulty_level.type.length >= required_length
    assert GeneratedQuestion.__table__.c.difficulty_level.type.length >= required_length


@pytest_asyncio.fixture
async def question_db_session(db_session):
    yield db_session


@pytest_asyncio.fixture
async def api_client(question_db_session):
    async def override_get_db():
        yield question_db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


class FakeProvider:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []

    async def generate(self, messages):
        self.calls.append(messages)
        return {"content": next(self._responses)}


async def _create_user(db_session):
    user_id = uuid.uuid4()
    db_session.add(
        User(
            id=user_id,
            nickname="出题测试用户",
            email=f"question-{user_id}@example.com",
            password_hash="not-used-in-test",
            birth_date=date(2015, 1, 1),
            age_group="10-12",
        )
    )
    await db_session.commit()
    return user_id


async def _create_practice_batch(db_session, user_id, *, status="completed"):
    batch = GeneratedQuestionBatch(
        id=uuid.uuid4(),
        user_id=user_id,
        age_group_code="10-12",
        subject_code="数学",
        course_topic="综合练习",
        difficulty_level="medium",
        question_types=["choice", "multiple_choice", "fill_blank"],
        question_count=3,
        learning_goal="验证作答闭环",
        status=status,
        prompt_version="v-test",
    )
    questions = [
        GeneratedQuestion(
            id=uuid.uuid4(), batch_id=batch.id, user_id=user_id,
            subject_code="数学", course_topic="综合练习", difficulty_level="medium",
            question_type="choice", question_body="单选题", options=[{"key": "A", "value": "正确"}],
            correct_answer="A", explanation="单选解析", knowledge_tags=["单选"],
            source_prompt="test", quality_status="passed",
        ),
        GeneratedQuestion(
            id=uuid.uuid4(), batch_id=batch.id, user_id=user_id,
            subject_code="数学", course_topic="综合练习", difficulty_level="medium",
            question_type="multiple_choice", question_body="多选题",
            options=[{"key": key, "value": key} for key in ("A", "B", "C")],
            correct_answer="A,C", explanation="多选解析", knowledge_tags=["多选"],
            source_prompt="test", quality_status="passed",
        ),
        GeneratedQuestion(
            id=uuid.uuid4(), batch_id=batch.id, user_id=user_id,
            subject_code="数学", course_topic="综合练习", difficulty_level="medium",
            question_type="fill_blank", question_body="填空题", options=None,
            correct_answer="42", explanation="填空解析", knowledge_tags=["填空"],
            source_prompt="test", quality_status="passed",
        ),
        GeneratedQuestion(
            id=uuid.uuid4(), batch_id=batch.id, user_id=user_id,
            subject_code="数学", course_topic="综合练习", difficulty_level="medium",
            question_type="choice", question_body="审题未通过题", options=[{"key": "A", "value": "A"}],
            correct_answer="A", explanation="不应可提交", knowledge_tags=["失败"],
            source_prompt="test", quality_status="failed",
        ),
    ]
    db_session.add(batch)
    db_session.add_all(questions)
    await db_session.flush()
    return batch, questions


def _override_generation_dependencies(user_id, provider, monkeypatch):
    async def override_user_id():
        return user_id

    app.dependency_overrides[get_current_user_id] = override_user_id
    monkeypatch.setattr(
        questions_api,
        "get_ai_provider",
        lambda: provider,
        raising=False,
    )


def _clear_generation_dependencies():
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.mark.asyncio
async def test_generate_with_real_authenticated_session_uses_existing_transaction(
    api_client,
    question_db_session,
    monkeypatch,
):
    user_id = await _create_user(question_db_session)
    provider = FakeProvider(
        [
            json.dumps([GENERATED_QUESTION], ensure_ascii=False),
            json.dumps({"passed": True, "revision_notes": ""}, ensure_ascii=False),
        ]
    )
    monkeypatch.setattr(questions_api, "get_ai_provider", lambda: provider)

    response = await api_client.post(
        "/api/v1/questions/generate",
        json=REQUEST_PAYLOAD,
        headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_generate_persists_reviewed_questions(
    api_client,
    question_db_session,
    monkeypatch,
):
    user_id = await _create_user(question_db_session)
    provider = FakeProvider(
        [
            json.dumps([GENERATED_QUESTION], ensure_ascii=False),
            json.dumps({"passed": True, "revision_notes": ""}, ensure_ascii=False),
        ]
    )
    _override_generation_dependencies(user_id, provider, monkeypatch)

    try:
        response = await api_client.post("/api/v1/questions/generate", json=REQUEST_PAYLOAD)
    finally:
        _clear_generation_dependencies()

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["total_generated"] == 1
    assert len(payload["data"]["questions"]) == 1
    generated_payload = payload["data"]["questions"][0]
    assert generated_payload["question_body"] == GENERATED_QUESTION["question_body"]
    assert "correct_answer" not in generated_payload
    assert "explanation" not in generated_payload
    assert "is_correct" not in generated_payload["options"][0]
    assert "correct_answer" not in generated_payload["options"][0]["metadata"]
    assert "analysis" not in generated_payload["options"][0]["metadata"]
    assert generated_payload["options"][0]["metadata"]["safe_hint"] == "先观察分母"
    batch_id = uuid.UUID(payload["data"]["batch_id"])

    batch = await question_db_session.get(GeneratedQuestionBatch, batch_id)
    assert batch is not None
    assert batch.status == "completed"

    questions = list(
        (
            await question_db_session.execute(
                select(GeneratedQuestion).where(GeneratedQuestion.batch_id == batch_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(questions) == 1
    assert questions[0].quality_status == "passed"
    expected_hash = hashlib.sha256(
        GENERATED_QUESTION["question_body"].strip().encode("utf-8")
    ).hexdigest()
    assert questions[0].similarity_hash == expected_hash

    checks = list(
        (
            await question_db_session.execute(
                select(QuestionQualityCheck).where(
                    QuestionQualityCheck.generated_question_id == questions[0].id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(checks) == 1
    assert checks[0].status == "passed"

    memory = await QuestionMemoryTool(question_db_session).search_similar_questions(
        str(user_id), "数学", "分数加法"
    )
    assert memory["total"] == 1
    assert memory["questions"][0]["similarity_hash"] == expected_hash


@pytest.mark.asyncio
async def test_batch_detail_and_variant_are_scoped_to_current_user(
    api_client,
    question_db_session,
    monkeypatch,
):
    owner_id = await _create_user(question_db_session)
    provider = FakeProvider(
        [
            json.dumps([GENERATED_QUESTION], ensure_ascii=False),
            json.dumps({"passed": True, "revision_notes": ""}, ensure_ascii=False),
        ]
    )
    _override_generation_dependencies(owner_id, provider, monkeypatch)
    try:
        generated = await api_client.post("/api/v1/questions/generate", json=REQUEST_PAYLOAD)
        batch_id = generated.json()["data"]["batch_id"]
        owner_detail = await api_client.get(f"/api/v1/questions/batches/{batch_id}")
    finally:
        _clear_generation_dependencies()

    assert owner_detail.status_code == 200
    assert owner_detail.json()["code"] == "SUCCESS"
    owner_questions = owner_detail.json()["data"]["questions"]
    assert len(owner_questions) == 1
    assert "correct_answer" not in owner_questions[0]
    assert "explanation" not in owner_questions[0]
    assert "is_correct" not in owner_questions[0]["options"][0]
    assert "correct_answer" not in owner_questions[0]["options"][0]["metadata"]

    question_id = owner_questions[0]["id"]
    _override_generation_dependencies(owner_id, provider, monkeypatch)
    try:
        owner_variant = await api_client.post(
            "/api/v1/questions/variant",
            json={"question_id": question_id},
        )
        owner_history = await api_client.get("/api/v1/questions/history")
    finally:
        _clear_generation_dependencies()

    assert owner_variant.status_code == 200
    assert owner_variant.json()["data"]["parent_question_id"] == question_id
    assert owner_variant.json()["data"]["status"] == "queued"
    _override_generation_dependencies(owner_id, provider, monkeypatch)
    repeated_variant = await api_client.post(
        "/api/v1/questions/variant",
        json={"question_id": question_id},
    )
    assert repeated_variant.status_code == 200
    assert repeated_variant.json()["data"]["job_id"] == owner_variant.json()["data"]["job_id"]
    assert repeated_variant.json()["data"]["status"] == "queued"
    assert owner_history.status_code == 200
    assert owner_history.json()["data"]["items"]
    assert all(
        "correct_answer" not in item and "explanation" not in item
        for item in owner_history.json()["data"]["items"]
    )
    history_items_with_options = [
        item for item in owner_history.json()["data"]["items"] if item["options"]
    ]
    assert history_items_with_options
    assert all(
        "is_correct" not in item["options"][0]
        and "analysis" not in item["options"][0]["metadata"]
        for item in history_items_with_options
    )

    attacker_id = await _create_user(question_db_session)
    _override_generation_dependencies(attacker_id, provider, monkeypatch)
    try:
        foreign_detail = await api_client.get(f"/api/v1/questions/batches/{batch_id}")
        foreign_variant = await api_client.post(
            "/api/v1/questions/variant",
            json={"question_id": question_id},
        )
    finally:
        _clear_generation_dependencies()

    assert foreign_detail.status_code == 404
    assert foreign_detail.json()["message"] == "批次不存在"
    assert foreign_variant.status_code == 404
    assert foreign_variant.json()["message"] == "原题目不存在"


def test_question_and_batch_schemas_accept_orm_datetimes():
    now = datetime.now(timezone.utc)

    question = GeneratedQuestionResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "batch_id": uuid.uuid4(),
            "subject_code": "数学",
            "course_topic": "分数加法",
            "difficulty_level": "medium",
            "question_type": "choice",
            "question_body": "1/2 + 1/2 = ?",
            "options": [{"key": "A", "value": "1"}],
            "correct_answer": "A",
            "explanation": "同分母分数相加。",
            "knowledge_tags": ["分数"],
            "quality_status": "passed",
            "created_at": now,
        }
    )
    batch = BatchResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "age_group_code": "10-12",
            "subject_code": "数学",
            "course_topic": "分数加法",
            "difficulty_level": "medium",
            "question_types": ["choice"],
            "question_count": 1,
            "status": "completed",
            "prompt_version": "v1.0",
            "created_at": now,
        }
    )

    assert question.created_at == now
    assert batch.created_at == now


@pytest.mark.asyncio
async def test_generate_rolls_back_when_review_fails(
    api_client,
    question_db_session,
    monkeypatch,
):
    user_id = await _create_user(question_db_session)
    provider = FakeProvider(
        [
            response
            for _ in range(3)
            for response in (
                json.dumps([GENERATED_QUESTION], ensure_ascii=False),
                json.dumps(
                    {"passed": False, "revision_notes": "答案存在歧义"},
                    ensure_ascii=False,
                ),
            )
        ]
    )
    _override_generation_dependencies(user_id, provider, monkeypatch)

    try:
        response = await api_client.post("/api/v1/questions/generate", json=REQUEST_PAYLOAD)
    finally:
        _clear_generation_dependencies()

    assert response.status_code == 422
    assert response.json()["message"] == "题目未能通过审核，请调整条件后重试"
    batch_count = (
        await question_db_session.execute(
            select(func.count())
            .select_from(GeneratedQuestionBatch)
            .where(GeneratedQuestionBatch.user_id == user_id)
        )
    ).scalar_one()
    assert batch_count == 0
    assert len(provider.calls) == 6


@pytest.mark.asyncio
async def test_submit_completed_generated_batch_persists_feedback_and_replays_without_side_effects(
    api_client,
    question_db_session,
):
    assert "generated_practice_submissions" in Base.metadata.tables
    assert "generated_practice_answers" in Base.metadata.tables
    assert "generated_practice_reward_events" in Base.metadata.tables

    user_id = await _create_user(question_db_session)
    batch, questions = await _create_practice_batch(question_db_session, user_id)
    submission_id = uuid.uuid4()
    request = {
        "submission_id": str(submission_id),
        "answers": [
            {"question_id": str(questions[0].id), "user_answer": "a", "time_spent_seconds": 2},
            {"question_id": str(questions[1].id), "user_answer": " C, A ", "time_spent_seconds": 3},
            {"question_id": str(questions[2].id), "user_answer": " 42 ", "time_spent_seconds": 4},
        ],
    }

    async def override_user_id():
        return user_id

    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        first = await api_client.post(
            f"/api/v1/questions/batches/{batch.id}/submit", json=request
        )
        replay = await api_client.post(
            f"/api/v1/questions/batches/{batch.id}/submit", json=request
        )
    finally:
        _clear_generation_dependencies()

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["data"] == first.json()["data"]
    payload = first.json()["data"]
    assert payload["submission_id"] == str(submission_id)
    assert payload["batch_id"] == str(batch.id)
    assert payload["total_count"] == 3
    assert payload["correct_count"] == 3
    assert payload["accuracy_rate"] == 1.0
    assert payload["time_spent_seconds"] == 9
    assert [item["is_correct"] for item in payload["results"]] == [True, True, True]
    assert [item["correct_answer"] for item in payload["results"]] == ["A", "A,C", "42"]
    assert [item["explanation"] for item in payload["results"]] == ["单选解析", "多选解析", "填空解析"]

    assert (await question_db_session.execute(
        select(func.count()).select_from(Base.metadata.tables["generated_practice_submissions"])
    )).scalar_one() == 1
    assert (await question_db_session.execute(
        select(func.count()).select_from(Base.metadata.tables["generated_practice_answers"])
    )).scalar_one() == 3
    assert (await question_db_session.execute(
        select(func.count()).select_from(Base.metadata.tables["generated_practice_reward_events"])
    )).scalar_one() == 3

    user = await question_db_session.get(User, user_id)
    assert user.total_answered == 3
    assert user.correct_answered == 3
    first_score = user.total_score
    report = await BehaviorService(question_db_session).get_learning_report(user_id)
    assert report["overview"]["total_answered"] == 3
    assert report["subject_mastery"][0]["subject"] == "数学"

    # 已持久化聚合的原样重放不应受后续批次状态变化影响。
    batch.status = "failed"
    await question_db_session.flush()
    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        replay_after_state_change = await api_client.post(
            f"/api/v1/questions/batches/{batch.id}/submit", json=request
        )
    finally:
        _clear_generation_dependencies()
    assert replay_after_state_change.status_code == 200
    assert replay_after_state_change.json()["data"] == first.json()["data"]
    await question_db_session.refresh(user)
    assert user.total_answered == 3
    batch.status = "completed"
    await question_db_session.flush()

    second_request = {**request, "submission_id": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        second = await api_client.post(
            f"/api/v1/questions/batches/{batch.id}/submit", json=second_request
        )
    finally:
        _clear_generation_dependencies()
    assert second.status_code == 200
    await question_db_session.refresh(user)
    assert user.total_answered == 6
    assert user.correct_answered == 6
    assert user.total_score == first_score
    assert second.json()["data"]["gamification"]["points_earned"] == 0
    assert (await question_db_session.execute(
        select(func.count()).select_from(Base.metadata.tables["generated_practice_reward_events"])
    )).scalar_one() == 3

    # A persisted submission owns immutable answer snapshots. Replaying the
    # original request must not depend on mutable generated-question rows.
    await question_db_session.delete(questions[0])
    questions[1].question_type = "fill_blank"
    await question_db_session.commit()
    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        replay_after_question_changes = await api_client.post(
            f"/api/v1/questions/batches/{batch.id}/submit", json=request
        )
        changed_request = {
            **request,
            "answers": [dict(answer) for answer in request["answers"]],
        }
        changed_request["answers"][0]["user_answer"] = "B"
        conflict_after_question_changes = await api_client.post(
            f"/api/v1/questions/batches/{batch.id}/submit", json=changed_request
        )
    finally:
        _clear_generation_dependencies()
    assert replay_after_question_changes.status_code == 200
    assert replay_after_question_changes.json()["data"] == first.json()["data"]
    assert conflict_after_question_changes.status_code == 409


@pytest.mark.asyncio
async def test_submit_generated_batch_enforces_owner_state_exact_passed_set_and_idempotency_conflict(
    api_client,
    question_db_session,
):
    owner_id = await _create_user(question_db_session)
    attacker_id = await _create_user(question_db_session)
    batch, questions = await _create_practice_batch(question_db_session, owner_id)
    pending_batch, pending_questions = await _create_practice_batch(
        question_db_session, owner_id, status="pending"
    )
    submission_id = uuid.uuid4()
    complete_answers = [
        {"question_id": str(question.id), "user_answer": question.correct_answer, "time_spent_seconds": 1}
        for question in questions[:3]
    ]

    async def owner():
        return owner_id

    async def attacker():
        return attacker_id

    app.dependency_overrides[get_current_user_id] = attacker
    foreign = await api_client.post(
        f"/api/v1/questions/batches/{batch.id}/submit",
        json={"submission_id": str(submission_id), "answers": complete_answers},
    )
    app.dependency_overrides[get_current_user_id] = owner
    pending = await api_client.post(
        f"/api/v1/questions/batches/{pending_batch.id}/submit",
        json={
            "submission_id": str(uuid.uuid4()),
            "answers": [{"question_id": str(q.id), "user_answer": q.correct_answer, "time_spent_seconds": 1} for q in pending_questions[:3]],
        },
    )
    incomplete = await api_client.post(
        f"/api/v1/questions/batches/{batch.id}/submit",
        json={"submission_id": str(uuid.uuid4()), "answers": complete_answers[:2]},
    )
    unapproved = await api_client.post(
        f"/api/v1/questions/batches/{batch.id}/submit",
        json={"submission_id": str(uuid.uuid4()), "answers": complete_answers + [{"question_id": str(questions[3].id), "user_answer": "A", "time_spent_seconds": 1}]},
    )
    accepted = await api_client.post(
        f"/api/v1/questions/batches/{batch.id}/submit",
        json={"submission_id": str(submission_id), "answers": complete_answers},
    )
    conflict_answers = [dict(item) for item in complete_answers]
    conflict_answers[0]["user_answer"] = "B"
    conflict = await api_client.post(
        f"/api/v1/questions/batches/{batch.id}/submit",
        json={"submission_id": str(submission_id), "answers": conflict_answers},
    )
    _clear_generation_dependencies()

    assert foreign.status_code == 404
    assert foreign.json()["message"] == "批次不存在"
    assert pending.status_code == 409
    assert pending.json()["message"] == "该批次尚未完成，无法提交"
    assert incomplete.status_code == 422
    assert incomplete.json()["message"] == "请完整且仅提交本批次已通过审核的每一道题"
    assert unapproved.status_code == 422
    assert unapproved.json()["message"] == "请完整且仅提交本批次已通过审核的每一道题"
    assert accepted.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["message"] == "提交编号已用于不同的作答内容"


@pytest.mark.asyncio
async def test_concurrent_identical_generated_practice_submissions_commit_once(
    question_db_session,
):
    from app.services.generated_practice_service import submit_generated_practice

    user_id = await _create_user(question_db_session)
    batch, questions = await _create_practice_batch(question_db_session, user_id)
    await question_db_session.commit()
    submission_id = uuid.uuid4()
    request = GeneratedPracticeSubmitRequest.model_validate(
        {
            "submission_id": submission_id,
            "answers": [
                {
                    "question_id": question.id,
                    "user_answer": question.correct_answer,
                    "time_spent_seconds": 1,
                }
                for question in questions[:3]
            ],
        }
    )
    session_factory = async_sessionmaker(
        question_db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def submit_once():
        async with session_factory() as session:
            result = await submit_generated_practice(
                session, batch_id=batch.id, user_id=user_id, request=request
            )
            await session.commit()
            return result

    first, replay = await asyncio.gather(submit_once(), submit_once())

    assert first == replay
    assert (
        await question_db_session.execute(
            select(func.count()).select_from(GeneratedPracticeSubmission).where(
                GeneratedPracticeSubmission.id == submission_id
            )
        )
    ).scalar_one() == 1
    assert (
        await question_db_session.execute(
            select(func.count()).select_from(GeneratedPracticeAnswer).where(
                GeneratedPracticeAnswer.submission_id == submission_id
            )
        )
    ).scalar_one() == 3
    assert (
        await question_db_session.execute(
            select(func.count()).select_from(GeneratedPracticeRewardEvent).where(
                GeneratedPracticeRewardEvent.submission_id == submission_id
            )
        )
    ).scalar_one() == 3
    question_db_session.expire_all()
    user = await question_db_session.get(User, user_id)
    assert user.total_answered == 3
    assert user.correct_answered == 3


@pytest.mark.asyncio
async def test_generated_practice_injected_failure_rolls_back_all_side_effects(
    question_db_session, monkeypatch
):
    from app.services import generated_practice_service

    user_id = await _create_user(question_db_session)
    batch, questions = await _create_practice_batch(question_db_session, user_id)
    await question_db_session.commit()
    submission_id = uuid.uuid4()
    request = GeneratedPracticeSubmitRequest.model_validate(
        {
            "submission_id": submission_id,
            "answers": [
                {
                    "question_id": question.id,
                    "user_answer": question.correct_answer,
                    "time_spent_seconds": 1,
                }
                for question in questions[:3]
            ],
        }
    )
    original_reward = generated_practice_service.reward_generated_practice_answer
    calls = 0

    async def fail_after_first_reward(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = await original_reward(*args, **kwargs)
        if calls == 2:
            raise RuntimeError("injected generated-practice failure")
        return result

    monkeypatch.setattr(
        generated_practice_service,
        "reward_generated_practice_answer",
        fail_after_first_reward,
    )
    session_factory = async_sessionmaker(
        question_db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="injected generated-practice"):
            await generated_practice_service.submit_generated_practice(
                session, batch_id=batch.id, user_id=user_id, request=request
            )
        await session.rollback()

    for model, predicate in (
        (
            GeneratedPracticeSubmission,
            GeneratedPracticeSubmission.id == submission_id,
        ),
        (
            GeneratedPracticeAnswer,
            GeneratedPracticeAnswer.submission_id == submission_id,
        ),
        (
            GeneratedPracticeRewardEvent,
            GeneratedPracticeRewardEvent.submission_id == submission_id,
        ),
    ):
        assert (
            await question_db_session.execute(
                select(func.count()).select_from(model).where(predicate)
            )
        ).scalar_one() == 0
    question_db_session.expire_all()
    user = await question_db_session.get(User, user_id)
    assert user.total_answered == 0
    assert user.correct_answered == 0
    assert user.total_score == 0
    report = await BehaviorService(question_db_session).get_learning_report(user_id)
    assert report["overview"]["total_answered"] == 0
