import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest


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
