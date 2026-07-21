"""四 Agent 辅导与答题反馈 API 测试。"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.harness import TutorHarness
from app.core.database import get_db
from app.core.deps import get_current_user_id, get_current_user_id_optional
from app.main import app
from app.models.content import KnowledgeNode, Question
from app.models.learning import Answer, LearningSession


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
async def test_chat_returns_complete_chinese_fallback_when_harness_fails(monkeypatch):
    async def raise_harness_error(self, _context):
        raise RuntimeError("模拟辅导服务异常")

    monkeypatch.setattr(TutorHarness, "reply", raise_harness_error)

    response = await _post(
        "/api/v1/ai/chat",
        {"message": "我卡住了"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["messages"][0]["role"] == "teacher"
    assert data["diagnosis"]
    assert data["teaching_strategy"] == {
        "approach": "standard",
        "pace": "normal",
        "focus_area": "题意与条件",
    }
    assert data["mastery"] == 0.5
    assert all("RuntimeError" not in value for value in data["messages"][0].values())


@pytest.mark.asyncio
async def test_question_context_changes_guidance_without_leaking_answer_before_attempt():
    base_context = {"is_correct": False}
    fraction_response = await TutorHarness().reply(
        {
            **base_context,
            "question": {
                "question_text": "一个披萨平均分成四份，每份占整体的几分之几？",
                "knowledge_points": ["分数的意义"],
                "correct_answer": "保密答案：四分之一",
            },
        }
    )
    perimeter_response = await TutorHarness().reply(
        {
            **base_context,
            "question": {
                "question_text": "长方形长 8 厘米、宽 3 厘米，怎样求周长？",
                "knowledge_points": ["长方形周长"],
                "correct_answer": "保密答案：二十二厘米",
            },
        }
    )

    fraction_messages = "\n".join(message.content for message in fraction_response.messages)
    perimeter_messages = "\n".join(message.content for message in perimeter_response.messages)
    assert "披萨平均分成四份" in fraction_messages
    assert "分数的意义" in fraction_messages
    assert "长方形长 8 厘米" in perimeter_messages
    assert "长方形周长" in perimeter_messages
    assert fraction_messages != perimeter_messages
    assert "保密答案：四分之一" not in fraction_messages
    assert "保密答案：二十二厘米" not in perimeter_messages


@pytest.mark.asyncio
async def test_tutor_uses_student_attempt_when_context_contains_an_answer():
    response = await TutorHarness().reply(
        {
            "question": {
                "question_text": "9 支铅笔平均分给 3 人，每人几支？",
                "knowledge_points": ["平均分"],
                "correct_answer": "保密答案：三支",
            },
            "student_answer": "我先算 9 加 3。",
            "is_correct": False,
        }
    )

    messages = "\n".join(message.content for message in response.messages)
    assert "9 支铅笔平均分给 3 人" in messages
    assert "平均分" in messages
    assert "9 加 3" in messages
    assert "保密答案：三支" not in messages


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
    fake_db = _FakeSession(question, None)

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
    assert data["answer_verified"] is False
    assert "correct_answer" not in data["question"]
    assert "explanation" not in data["question"]


@pytest.mark.asyncio
async def test_explain_question_only_question_id_hides_answer_and_explanation():
    question_id = uuid.uuid4()
    knowledge_node_id = uuid.uuid4()
    question = Question(
        id=question_id,
        knowledge_node_id=knowledge_node_id,
        difficulty_level="DIFF_EASY",
        question_type="CHOICE",
        question_body="一个蛋糕平均分成三份，每份是多少？",
        correct_answer="三分之一",
        explanation="平均分成三份，就是把整体看作三等份。",
        knowledge_node_rel=KnowledgeNode(id=knowledge_node_id, title="平均分与分数"),
    )
    fake_db = _FakeSession(question)

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = await _post(
            "/api/v1/ai/explain-question",
            json={"question_id": str(question_id)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer_verified"] is False
    assert data["question"]["text"] == question.question_body
    assert "correct_answer" not in data["question"]
    assert "explanation" not in data["question"]


@pytest.mark.asyncio
async def test_explain_question_reveals_answer_only_after_server_verified_attempt():
    question_id = uuid.uuid4()
    knowledge_node_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    question = Question(
        id=question_id,
        knowledge_node_id=knowledge_node_id,
        difficulty_level="DIFF_EASY",
        question_type="CHOICE",
        question_body="一个蛋糕平均分成三份，每份是多少？",
        correct_answer="三分之一",
        explanation="平均分成三份，就是把整体看作三等份。",
        knowledge_node_rel=KnowledgeNode(id=knowledge_node_id, title="平均分与分数"),
    )
    answer = Answer(
        id=uuid.uuid4(),
        session_id=session_id,
        question_id=question_id,
        user_answer="三",
        is_correct=False,
        time_spent_seconds=8,
    )
    fake_db = _FakeSession(question, answer)

    async def override_get_db():
        yield fake_db

    async def override_optional_user_id():
        return user_id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id_optional] = override_optional_user_id
    try:
        response = await _post(
            "/api/v1/ai/explain-question",
            json={
                "question_id": str(question_id),
                "user_answer": "伪造答案",
                "is_correct": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer_verified"] is True
    assert data["question"]["correct_answer"] == "三分之一"
    assert data["question"]["explanation"] == question.explanation
    assert "你刚才写的是“伪造答案”" not in data["ai_reply"]["content"]
    assert "你刚才写的是“三”" in data["ai_reply"]["content"]


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
