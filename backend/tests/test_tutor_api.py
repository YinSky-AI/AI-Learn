"""四 Agent 辅导与答题反馈 API 测试。"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.harness import TutorHarness
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.main import app
from app.models.content import KnowledgeNode, Question
from app.models.learning import LearningSession


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, *results):
        self._results = list(results)
        self.added = []

    async def execute(self, _statement):
        return _ScalarResult(self._results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


async def _post(path: str, json: dict):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, json=json)


@pytest.mark.asyncio
async def test_tutor_harness_uses_four_socratic_roles_for_wrong_answer():
    harness = TutorHarness()

    response = await harness.reply(
        {
            "question": {
                "question_body": "把一个蛋糕平均分给三个人，应该怎样列式？",
                "correct_answer": "保密标准答案XYZ",
            },
            "student_answer": "我想用加法。",
            "is_correct": False,
            "frustrated": True,
        }
    )

    assert {message.role for message in response.messages} == {
        "teacher",
        "assistant",
        "diagnostician",
        "encourager",
    }
    assert response.suggested_next_step
    assert all("保密标准答案XYZ" not in message.content for message in response.messages)
    assert all(any("\u4e00" <= char <= "\u9fff" for char in message.content) for message in response.messages)


@pytest.mark.asyncio
async def test_encourager_only_joins_wrong_or_frustrated_contexts():
    response = await TutorHarness().reply(
        {
            "question": {"question_body": "说说你对分数的理解。"},
            "student_answer": "分数表示整体的一部分。",
            "is_correct": True,
        }
    )

    assert "encourager" not in {message.role for message in response.messages}


@pytest.mark.asyncio
async def test_diagnosis_updates_strategy_consumed_by_later_agents():
    response = await TutorHarness().reply(
        {
            "question": {"question_body": "十二个苹果平均分给三个人，每人几个？"},
            "student_answer": "十二加三。",
            "is_correct": False,
            "mastery": 0.6,
        }
    )

    messages = {message.role: message.content for message in response.messages}
    assert response.teaching_strategy["approach"] == "simplified"
    assert response.teaching_strategy["pace"] == "slow"
    assert response.mastery < 0.6
    assert "放慢" in messages["teacher"]
    assert "拆成" in messages["assistant"]


@pytest.mark.asyncio
async def test_conversation_history_changes_socratic_follow_up():
    context = {
        "question": {"question_body": "怎样理解三分之一？"},
        "student_answer": "我还不确定。",
        "is_correct": False,
    }
    without_history = await TutorHarness().reply(context)
    with_history = await TutorHarness().reply(
        {
            **context,
            "conversation_history": [
                {"role": "user", "content": "我想先画图，把整体分成三份。"},
                {"role": "assistant", "content": "这个方向可以继续。"},
            ],
        }
    )

    plain_prompt = next(
        message.content for message in without_history.messages if message.role == "assistant"
    )
    history_prompt = next(
        message.content for message in with_history.messages if message.role == "assistant"
    )
    assert history_prompt != plain_prompt
    assert "上一轮" in history_prompt
    assert "画图" in history_prompt


@pytest.mark.asyncio
async def test_chat_returns_four_role_messages_for_wrong_answer():
    response = await _post(
        "/api/v1/ai/chat",
        {
            "message": "我不知道为什么做错了。",
            "context": {
                "question": {
                    "question_body": "把一个蛋糕平均分给三个人，应该怎样列式？",
                    "correct_answer": "保密标准答案XYZ",
                },
                "student_answer": "我想用加法。",
                "is_correct": False,
                "frustrated": True,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "SUCCESS"
    assert {message["role"] for message in body["data"]["messages"]} == {
        "teacher",
        "assistant",
        "diagnostician",
        "encourager",
    }
    assert body["data"]["suggested_next_step"]


@pytest.mark.asyncio
async def test_wrong_answer_returns_explanation_knowledge_point_and_tutor_prompt():
    session_id = uuid.uuid4()
    question_id = uuid.uuid4()
    knowledge_node_id = uuid.uuid4()
    user_id = uuid.uuid4()

    learning_session = LearningSession(
        id=session_id,
        user_id=user_id,
        knowledge_node_id=knowledge_node_id,
        difficulty_level="DIFF_EASY",
        status="in_progress",
        correct_count=0,
        total_questions=0,
    )
    knowledge_node = KnowledgeNode(id=knowledge_node_id, title="平均分与分数")
    question = Question(
        id=question_id,
        knowledge_node_id=knowledge_node_id,
        difficulty_level="DIFF_EASY",
        question_type="CHOICE",
        question_body="一个蛋糕平均分成三份，每份是多少？",
        correct_answer="三分之一",
        explanation="平均分成三份，就是把整体看作三等份。",
        knowledge_node_rel=knowledge_node,
    )
    fake_db = _FakeSession(learning_session, question)

    async def override_get_db():
        yield fake_db

    async def override_user_id():
        return user_id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_user_id
    try:
        response = await _post(
            f"/api/v1/learning/sessions/{session_id}/answer",
            json={
                "question_id": str(question_id),
                "user_answer": "三",
                "time_spent_seconds": 12,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_correct"] is False
    assert data["explanation"] == "平均分成三份，就是把整体看作三等份。"
    assert data["knowledge_point"] == "平均分与分数"
    assert data["tutor_prompt"]
    assert "三分之一" not in data["tutor_prompt"]


@pytest.mark.asyncio
async def test_explain_question_returns_question_context_and_first_tutor_reply():
    question_id = uuid.uuid4()
    knowledge_node_id = uuid.uuid4()
    knowledge_node = KnowledgeNode(id=knowledge_node_id, title="平均分与分数")
    question = Question(
        id=question_id,
        knowledge_node_id=knowledge_node_id,
        difficulty_level="DIFF_EASY",
        question_type="CHOICE",
        question_body="一个蛋糕平均分成三份，每份是多少？",
        correct_answer="三分之一",
        explanation="平均分成三份，就是把整体看作三等份。",
        knowledge_node_rel=knowledge_node,
    )
    fake_db = _FakeSession(question)

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = await _post(
            "/api/v1/ai/explain-question",
            json={
                "question_id": str(question_id),
                "user_answer": "三",
                "is_correct": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["question"]["text"] == question.question_body
    assert data["question"]["knowledge_point"] == "平均分与分数"
    assert data["ai_reply"]["content"]
    assert data["ai_reply"]["role"] == "teacher"


@pytest.mark.asyncio
async def test_explain_question_returns_chinese_not_found_error():
    fake_db = _FakeSession(None)

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = await _post(
            "/api/v1/ai/explain-question",
            json={"question_id": str(uuid.uuid4())},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["message"] == "题目不存在"
