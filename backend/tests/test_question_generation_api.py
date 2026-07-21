import hashlib
import json
import os
import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.ai.tools.question_memory_tool import QuestionMemoryTool
from app.api.v1 import questions as questions_api
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.main import app
from app.models import Base
from app.models.ai_generated import (
    GeneratedQuestion,
    GeneratedQuestionBatch,
    QuestionQualityCheck,
)
from app.models.user import User


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
        {"key": "A", "value": "八分之五"},
        {"key": "B", "value": "八分之六"},
    ],
    "correct_answer": "A",
    "explanation": "同分母分数相加，分母不变，分子相加。",
    "tags": ["同分母分数加法"],
    "difficulty": "medium",
}


@pytest_asyncio.fixture
async def question_db_session():
    database_url = os.getenv(
        "QUESTION_TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/learning_platform_test",
    )
    test_engine = create_async_engine(database_url, poolclass=NullPool)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


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
