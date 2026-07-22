import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest


def test_review_scheduler_is_deterministic_and_distinguishes_success():
    from app.services.wrong_book_service import calculate_next_review_at

    now = datetime(2026, 1, 1, 0, 0, 0)
    assert (calculate_next_review_at(now=now, is_correct=True, review_count=0) - now).days == 1
    assert (calculate_next_review_at(now=now, is_correct=True, review_count=3) - now).days == 14
    assert (calculate_next_review_at(now=now, is_correct=False, review_count=3) - now).days == 1


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class _FakeSession:
    def __init__(self, *records):
        self.records = list(records)
        self.added = []
        self.flushed = False
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _ScalarResult(self.records.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushed = True


class _SubmissionSession:
    def __init__(self, *records):
        self.records = list(records)
        self.added = []
        self.flush_count = 0

    async def execute(self, _statement):
        return _ScalarResult(self.records.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1


class _ScalarsCollection:
    def __init__(self, values):
        self.values = values

    def unique(self):
        return self

    def all(self):
        return self.values


class _ListResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return _ScalarsCollection(self.values)


class _ListSession:
    def __init__(self):
        self.results = [_ScalarResult(0), _ListResult([])]

    async def execute(self, _statement):
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_list_questions_uses_sqlalchemy_scalars_result_api():
    from app.services.wrong_book_service import WrongBookService

    records, total = await WrongBookService(_ListSession()).list_questions(
        user_id=uuid.uuid4(),
        subject=None,
        knowledge_point=None,
        is_mastered=False,
        page=1,
        page_size=20,
    )

    assert records == []
    assert total == 0


@pytest.mark.asyncio
async def test_record_wrong_answer_uses_event_deduplication_then_upsert():
    from app.services.wrong_book_service import WrongBookService

    existing = SimpleNamespace(
        wrong_count=2,
        last_wrong_at=None,
        last_wrong_answer="旧答案",
        is_mastered=True,
        mastered_at=datetime.utcnow(),
    )
    session = _FakeSession(object(), existing)

    result = await WrongBookService(session).record_wrong_answer(
        user_id=uuid.uuid4(),
        question_id=uuid.uuid4(),
        answer_id=uuid.uuid4(),
        subject="数学",
        wrong_answer="B",
    )

    assert result is existing
    assert len(session.statements) == 2
    event_sql = str(session.statements[0].compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()))
    upsert_sql = str(session.statements[1].compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()))
    assert "ON CONFLICT (answer_id) DO NOTHING" in event_sql
    assert "ON CONFLICT ON CONSTRAINT uq_wrong_question_user_question DO UPDATE" in upsert_sql
    assert session.added == []
    assert session.flushed is True


@pytest.mark.asyncio
async def test_record_wrong_answer_does_not_increment_for_retried_answer_event():
    from app.services.wrong_book_service import WrongBookService

    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    session = _FakeSession(None)

    result = await WrongBookService(session).record_wrong_answer(
        user_id=user_id,
        question_id=question_id,
        answer_id=uuid.uuid4(),
        subject="数学",
        wrong_answer="C",
    )

    assert result is None
    assert len(session.statements) == 1
    assert session.added == []
    assert session.flushed is False


@pytest.mark.asyncio
async def test_new_answer_is_flushed_before_wrong_event_is_written(monkeypatch):
    from app.services import learning_service
    from app.services.wrong_book_service import WrongBookService

    user_id, session_id, question_id, answer_id = (uuid.uuid4() for _ in range(4))
    learning_session = SimpleNamespace(user_id=user_id, status="in_progress", total_questions=0, correct_count=0)
    question = SimpleNamespace(
        question_type="CHOICE", correct_answer="A", explanation="解析", id=question_id,
        knowledge_node_rel=SimpleNamespace(title="知识点", subject_code="数学"),
    )
    db = _SubmissionSession(learning_session, None, question, None)

    async def verify_flush_before_event(self, **_kwargs):
        assert db.flush_count >= 1
        return None

    monkeypatch.setattr(WrongBookService, "record_wrong_answer", verify_flush_before_event)
    result = await learning_service.submit_answer(
        db, session_id, user_id, question_id, answer_id, "B", 3
    )

    assert result["id"] == answer_id
    assert learning_session.total_questions == 1


@pytest.mark.asyncio
async def test_retried_answer_id_returns_existing_result_without_new_side_effects(monkeypatch):
    from app.models.learning import Answer
    from app.services import learning_service
    from app.services.wrong_book_service import WrongBookService

    user_id, session_id, question_id, answer_id = (uuid.uuid4() for _ in range(4))
    learning_session = SimpleNamespace(user_id=user_id, status="completed", total_questions=1, correct_count=0)
    question = SimpleNamespace(
        question_type="CHOICE", correct_answer="A", explanation="解析", id=question_id,
        knowledge_node_rel=SimpleNamespace(title="知识点", subject_code="数学"),
    )
    existing = Answer(id=answer_id, session_id=session_id, question_id=question_id, user_answer="B", is_correct=False, time_spent_seconds=3)
    db = _SubmissionSession(learning_session, existing, question, None)

    async def should_not_record(self, **_kwargs):
        raise AssertionError("重试不应再次收录错题")

    monkeypatch.setattr(WrongBookService, "record_wrong_answer", should_not_record)
    result = await learning_service.submit_answer(db, session_id, user_id, question_id, answer_id, "B", 3)

    assert result["id"] == answer_id
    assert db.added == []
    assert db.flush_count == 0
    assert learning_session.total_questions == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("session_id", uuid.uuid4()), ("question_id", uuid.uuid4()), ("user_answer", "A"), ("time_spent_seconds", 9)])
async def test_retried_answer_id_rejects_every_mismatched_payload_field(field, value):
    from fastapi import HTTPException
    from app.models.learning import Answer
    from app.services import learning_service

    user_id, session_id, question_id, answer_id = (uuid.uuid4() for _ in range(4))
    learning_session = SimpleNamespace(user_id=user_id, status="completed", total_questions=1, correct_count=0)
    existing = Answer(id=answer_id, session_id=session_id, question_id=question_id, user_answer="B", is_correct=False, time_spent_seconds=3)
    db = _SubmissionSession(learning_session, existing)
    request = {"session_id": session_id, "question_id": question_id, "user_answer": "B", "time_spent_seconds": 3}
    request[field] = value

    with pytest.raises(HTTPException, match="作答事件与原请求不一致") as error:
        await learning_service.submit_answer(db, user_id=user_id, answer_id=answer_id, **request)
    assert error.value.status_code == 409
    assert db.records == []


@pytest.mark.asyncio
async def test_replayed_answer_with_deleted_original_question_returns_safe_error():
    from fastapi import HTTPException
    from app.models.learning import Answer
    from app.services import learning_service

    user_id, session_id, question_id, answer_id = (uuid.uuid4() for _ in range(4))
    session = SimpleNamespace(user_id=user_id, status="completed", total_questions=1, correct_count=0)
    existing = Answer(id=answer_id, session_id=session_id, question_id=question_id, user_answer="B", is_correct=False, time_spent_seconds=3)
    db = _SubmissionSession(session, existing, None)

    with pytest.raises(HTTPException, match="原题已删除，无法回放该作答结果") as error:
        await learning_service.submit_answer(db, session_id, user_id, question_id, answer_id, "B", 3)
    assert error.value.status_code == 410


@pytest.mark.asyncio
async def test_answer_question_must_belong_to_session_knowledge_node():
    from fastapi import HTTPException
    from app.services import learning_service

    user_id, session_id, session_node_id, other_node_id, question_id, answer_id = (
        uuid.uuid4() for _ in range(6)
    )
    learning_session = SimpleNamespace(
        user_id=user_id,
        knowledge_node_id=session_node_id,
        status="in_progress",
        total_questions=0,
        correct_count=0,
    )
    question = SimpleNamespace(
        id=question_id,
        knowledge_node_id=other_node_id,
        question_type="CHOICE",
        correct_answer="A",
        explanation="解析",
        knowledge_node_rel=None,
    )
    db = _SubmissionSession(learning_session, None, question)

    with pytest.raises(HTTPException, match="题目不属于本次学习会话") as error:
        await learning_service.submit_answer(
            db, session_id, user_id, question_id, answer_id, "A", 3
        )

    assert error.value.status_code == 400
    assert db.added == []
