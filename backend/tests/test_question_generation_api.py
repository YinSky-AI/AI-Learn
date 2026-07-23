import hashlib
import json
import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.ai.tools.question_memory_tool import QuestionMemoryTool
from app.api.v1 import questions as questions_api
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.security import create_access_token
from app.main import app
from app.models.ai_generated import (
    GeneratedQuestion,
    GeneratedQuestionBatch,
    QuestionQualityCheck,
)
from app.models.user import User
from app.schemas.question import BatchResponse, GeneratedQuestionResponse


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
    assert owner_variant.json()["data"]["status"] == "failed"
    _override_generation_dependencies(owner_id, provider, monkeypatch)
    repeated_variant = await api_client.post(
        "/api/v1/questions/variant",
        json={"question_id": question_id},
    )
    assert repeated_variant.status_code == 200
    assert repeated_variant.json()["data"]["variant_id"] == owner_variant.json()["data"]["variant_id"]
    assert repeated_variant.json()["data"]["status"] == "failed"
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
