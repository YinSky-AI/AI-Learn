import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.flushed = False

    async def execute(self, _statement):
        return _ScalarResult(self.existing)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushed = True


@pytest.mark.asyncio
async def test_add_wrong_question_updates_existing_record_without_duplicate():
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
    assert existing.wrong_count == 3
    assert existing.last_wrong_answer == "B"
    assert existing.is_mastered is False
    assert existing.mastered_at is None
    assert session.added == []
    assert session.flushed is True


@pytest.mark.asyncio
async def test_add_wrong_question_creates_an_unmastered_record():
    from app.services.wrong_book_service import WrongBookService

    user_id = uuid.uuid4()
    question_id = uuid.uuid4()
    session = _FakeSession()

    result = await WrongBookService(session).add_wrong_question(
        user_id=user_id,
        question_id=question_id,
        subject="数学",
        wrong_answer="C",
    )

    assert result.user_id == user_id
    assert result.question_id == question_id
    assert result.subject == "数学"
    assert result.wrong_count == 1
    assert result.is_mastered is False
    assert session.added == [result]
    assert session.flushed is True
