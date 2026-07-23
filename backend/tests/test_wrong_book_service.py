import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def test_review_scheduler_is_deterministic_and_distinguishes_success():
    from app.services.wrong_book_service import calculate_next_review_at

    now = datetime(2026, 1, 1, 0, 0, 0)
    assert (calculate_next_review_at(now=now, is_correct=True, review_count=0) - now).days == 1
    assert (calculate_next_review_at(now=now, is_correct=True, review_count=3) - now).days == 14
    assert (calculate_next_review_at(now=now, is_correct=False, review_count=3) - now).days == 1


def test_multiple_choice_judging_uses_comma_delimited_option_sets():
    from app.services.learning_service import judge_answer

    question = SimpleNamespace(question_type="MULTIPLE_CHOICE", correct_answer="A,C")
    assert judge_answer(question, " C, A ") is True
    assert judge_answer(question, "CA,") is False
    assert judge_answer(question, "A,A,C") is False


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


@pytest.mark.asyncio
async def test_wrong_book_practice_attempt_replays_without_incrementing_review_count(db_session):
    from datetime import date, timezone
    from fastapi import HTTPException
    from app.models.content import AgeGroup, KnowledgeNode, Question, Subject
    from app.models.user import User
    from app.models.wrong_book import WrongQuestion
    from app.services.wrong_book_service import WrongBookService

    user_id, node_id, question_id = (uuid.uuid4() for _ in range(3))
    db_session.add_all([
        Subject(code="SUBJ_WB", name="错题幂等测试", sort_order=0),
        AgeGroup(code="AGE_WB", name="测试年龄", min_age=10, max_age=12, theme_config={}),
        User(
            id=user_id, nickname="错题用户", email=f"wrong-{user_id}@example.test",
            password_hash="hash", birth_date=date(2012, 1, 1), age_group="AGE_WB",
        ),
        KnowledgeNode(
            id=node_id, title="集合判题", subject_code="SUBJ_WB", age_group_code="AGE_WB",
            difficulty_level="DIFF_EASY", content_type="TYPE_QUIZ", content_body="测试",
        ),
    ])
    await db_session.flush()
    db_session.add(Question(
        id=question_id, knowledge_node_id=node_id, difficulty_level="DIFF_EASY",
        question_type="MULTIPLE_CHOICE", question_body="请选择", options=[{"key": "A"}, {"key": "C"}],
        correct_answer="A,C", explanation="集合相等",
    ))
    db_session.add(WrongQuestion(
        user_id=user_id, question_id=question_id, subject="数学", wrong_count=1,
        first_wrong_at=datetime.now(timezone.utc), last_wrong_at=datetime.now(timezone.utc),
        next_review_at=datetime.now(timezone.utc),
    ))
    await db_session.flush()
    attempt_id = uuid.uuid4()
    service = WrongBookService(db_session)

    first = await service.submit_practice_answer(
        user_id, question_id, "C,A", attempt_id=attempt_id
    )
    replay = await service.submit_practice_answer(
        user_id, question_id, "C,A", attempt_id=attempt_id
    )
    record = (await db_session.execute(
        __import__("sqlalchemy").select(WrongQuestion).where(
            WrongQuestion.user_id == user_id, WrongQuestion.question_id == question_id
        )
    )).scalar_one()

    assert first == replay
    assert first["is_correct"] is True
    assert record.review_count == 1
    with pytest.raises(HTTPException, match="练习尝试编号已用于不同的作答内容") as error:
        await service.submit_practice_answer(
            user_id, question_id, "A", attempt_id=attempt_id
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_wrong_book_practice_payload_includes_question_type(monkeypatch):
    from app.api.v1 import wrong_book as wrong_book_api

    question = SimpleNamespace(
        id=uuid.uuid4(), question_body="多选题", options=[],
        difficulty_level="DIFF_EASY", question_type="MULTIPLE_CHOICE",
    )

    async def fake_practice(_self, _user_id, _subject, _count):
        return [question]

    monkeypatch.setattr(wrong_book_api.WrongBookService, "get_practice_questions", fake_practice)
    response = await wrong_book_api.get_practice(
        subject=None, count=5, user_id=uuid.uuid4(), db=object()
    )

    assert response["data"]["questions"][0]["question_type"] == "MULTIPLE_CHOICE"


def test_wrong_book_practice_attempt_id_is_temporarily_optional():
    from app.api.v1.wrong_book import PracticeAnswerSubmit

    assert PracticeAnswerSubmit.model_fields["attempt_id"].is_required() is False


@pytest.mark.asyncio
async def test_wrong_book_api_generates_attempt_id_when_legacy_client_omits_it(monkeypatch):
    from app.api.v1 import wrong_book as wrong_book_api

    captured = {}

    async def fake_submit(_self, user_id, question_id, user_answer, *, attempt_id):
        captured.update(
            user_id=user_id,
            question_id=question_id,
            user_answer=user_answer,
            attempt_id=attempt_id,
        )
        return {"found": True, "is_correct": True}

    monkeypatch.setattr(
        wrong_book_api.WrongBookService, "submit_practice_answer", fake_submit
    )
    user_id, question_id = uuid.uuid4(), uuid.uuid4()
    request = wrong_book_api.PracticeAnswerSubmit(
        question_id=question_id, user_answer="A"
    )

    await wrong_book_api.submit_practice_answer(request, user_id=user_id, db=object())

    assert captured["user_id"] == user_id
    assert captured["question_id"] == question_id
    assert isinstance(captured["attempt_id"], uuid.UUID)


async def _create_real_wrong_practice_record(db_session, *, suffix: str):
    from app.models.content import AgeGroup, KnowledgeNode, Question, Subject
    from app.models.user import User
    from app.models.wrong_book import WrongQuestion

    user_id, node_id, question_id = (uuid.uuid4() for _ in range(3))
    subject_code = f"WB_{suffix}"
    age_code = f"WA_{suffix}"
    db_session.add_all(
        [
            Subject(code=subject_code, name="Wrong practice", sort_order=0),
            AgeGroup(
                code=age_code,
                name="Wrong practice age",
                min_age=10,
                max_age=12,
                theme_config={},
            ),
            User(
                id=user_id,
                nickname="Wrong practice user",
                email=f"wrong-practice-{user_id}@example.test",
                password_hash="hash",
                birth_date=date(2012, 1, 1),
                age_group=age_code,
            ),
            KnowledgeNode(
                id=node_id,
                title="Sets",
                subject_code=subject_code,
                age_group_code=age_code,
                difficulty_level="DIFF_EASY",
                content_type="TYPE_QUIZ",
                content_body="test",
            ),
        ]
    )
    await db_session.flush()
    question = Question(
        id=question_id,
        knowledge_node_id=node_id,
        difficulty_level="DIFF_EASY",
        question_type="MULTIPLE_CHOICE",
        question_body="Choose",
        options=[{"key": "A"}, {"key": "C"}],
        correct_answer="A,C",
        explanation="Both",
    )
    db_session.add_all(
        [
            question,
            WrongQuestion(
                user_id=user_id,
                question_id=question_id,
                subject="Math",
                wrong_count=1,
                first_wrong_at=datetime.now(timezone.utc),
                last_wrong_at=datetime.now(timezone.utc),
                next_review_at=datetime.now(timezone.utc),
            ),
        ]
    )
    await db_session.commit()
    return user_id, question_id, question


@pytest.mark.asyncio
async def test_concurrent_wrong_practice_attempts_preserve_both_schedule_updates(db_session):
    from app.models.wrong_book import WrongPracticeAttempt, WrongQuestion
    from app.services.wrong_book_service import WrongBookService

    user_id, question_id, _ = await _create_real_wrong_practice_record(
        db_session, suffix="CONC"
    )
    session_factory = async_sessionmaker(
        db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def submit_once():
        async with session_factory() as session:
            result = await WrongBookService(session).submit_practice_answer(
                user_id, question_id, "C,A", attempt_id=uuid.uuid4()
            )
            await session.commit()
            return result

    results = await asyncio.gather(submit_once(), submit_once())

    assert all(result["is_correct"] is True for result in results)
    db_session.expire_all()
    record = (
        await db_session.execute(
            select(WrongQuestion).where(
                WrongQuestion.user_id == user_id,
                WrongQuestion.question_id == question_id,
            )
        )
    ).scalar_one()
    attempt_count = (
        await db_session.execute(
            select(func.count()).select_from(WrongPracticeAttempt).where(
                WrongPracticeAttempt.user_id == user_id,
                WrongPracticeAttempt.question_id == question_id,
            )
        )
    ).scalar_one()
    assert attempt_count == 2
    assert record.review_count == 2
    assert record.difficulty_factor == 120


@pytest.mark.asyncio
async def test_wrong_practice_replay_uses_immutable_request_snapshot_and_logs_safely(
    db_session, caplog
):
    from fastapi import HTTPException
    from app.models.wrong_book import WrongPracticeAttempt
    from app.services.wrong_book_service import WrongBookService

    user_id, question_id, question = await _create_real_wrong_practice_record(
        db_session, suffix="SNAP"
    )
    attempt_id = uuid.uuid4()
    service = WrongBookService(db_session)
    with caplog.at_level(logging.INFO, logger="app.services.wrong_book_service"):
        first = await service.submit_practice_answer(
            user_id, question_id, " C, A ", attempt_id=attempt_id
        )
        await db_session.commit()
        await db_session.delete(question)
        await db_session.commit()
        replay = await service.submit_practice_answer(
            user_id, question_id, " C, A ", attempt_id=attempt_id
        )
        with pytest.raises(HTTPException) as error:
            await service.submit_practice_answer(
                user_id, question_id, "A", attempt_id=attempt_id
            )

    assert replay == first
    assert error.value.status_code == 409
    assert await db_session.get(WrongPracticeAttempt, attempt_id) is not None
    log_text = caplog.text
    assert "result=created" in log_text
    assert "result=replayed" in log_text
    assert "result=conflict" in log_text
    assert "attempt_key=" in log_text
    assert str(user_id) not in log_text
    assert "C, A" not in log_text
