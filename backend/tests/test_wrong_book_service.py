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
    def __init__(self, record=None):
        self.record = record
        self.added = []
        self.flushed = False
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _ScalarResult(self.record)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushed = True


@pytest.mark.asyncio
async def test_add_wrong_question_uses_single_postgresql_upsert_for_existing_record():
    from app.services.wrong_book_service import WrongBookService

    existing = SimpleNamespace(
        wrong_count=2,
        last_wrong_at=None,
        last_wrong_answer="旧答案",
        is_mastered=True,
        mastered_at=datetime.utcnow(),
    )
    session = _FakeSession(existing)

    result = await WrongBookService(session).add_wrong_question(
        user_id=uuid.uuid4(),
        question_id=uuid.uuid4(),
        subject="数学",
        wrong_answer="B",
    )

    assert result is existing
    assert len(session.statements) == 1
    compiled = str(session.statements[0].compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()))
    assert "ON CONFLICT ON CONSTRAINT uq_wrong_question_user_question DO UPDATE" in compiled
    assert session.added == []
    assert session.flushed is True


@pytest.mark.asyncio
async def test_add_wrong_question_returns_upserted_record_for_first_wrong_answer():
    from app.services.wrong_book_service import WrongBookService

    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    expected = SimpleNamespace(
        user_id=user_id, question_id=question_id, subject="数学", wrong_count=1, is_mastered=False
    )
    session = _FakeSession(expected)

    result = await WrongBookService(session).add_wrong_question(
        user_id=user_id,
        question_id=question_id,
        subject="数学",
        wrong_answer="C",
    )

    assert result is expected
    assert session.added == []
    assert session.flushed is True
