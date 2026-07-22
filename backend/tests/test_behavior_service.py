import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.behavior_service import BehaviorService


class _Session:
    def __init__(self, user):
        self.user = user
        self.flushes = 0

    async def get(self, model, user_id):
        return self.user if user_id == self.user.id else None

    async def flush(self):
        self.flushes += 1


@pytest.mark.asyncio
async def test_answer_event_updates_mastery_and_ignores_same_persisted_answer_id():
    user = SimpleNamespace(id=uuid.uuid4(), behavior_profile=None)
    session = _Session(user)
    service = BehaviorService(session)
    question = SimpleNamespace(
        knowledge_node_rel=SimpleNamespace(title="一元一次方程", subject_code="math"),
    )
    answer_id = uuid.uuid4()

    first = await service.update_after_answer(
        user_id=user.id,
        answer_id=answer_id,
        question=question,
        is_correct=True,
        response_time_ms=90_000,
        answered_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )
    duplicate = await service.update_after_answer(
        user_id=user.id,
        answer_id=answer_id,
        question=question,
        is_correct=True,
        response_time_ms=90_000,
        answered_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )

    mastery = first["knowledge_mastery"]["一元一次方程"]
    assert mastery["total"] == 1
    assert mastery["correct"] == 1
    assert mastery["level"] == pytest.approx(0.65)
    assert first["subject_mastery"]["math"]["level"] == 1
    assert first["study_stats"]["total_time_minutes"] == pytest.approx(1.5)
    assert duplicate["knowledge_mastery"]["一元一次方程"]["total"] == 1
    assert session.flushes == 1


@pytest.mark.asyncio
async def test_report_is_user_scoped_and_includes_requested_date_range():
    user = SimpleNamespace(
        id=uuid.uuid4(),
        behavior_profile={
            "knowledge_mastery": {
                "薄弱点": {"level": 0.2, "total": 2, "correct": 0},
                "强项": {"level": 0.8, "total": 3, "correct": 3},
            },
            "subject_mastery": {"math": {"level": 0.6, "total": 5, "correct": 3}},
            "study_stats": {
                "total_time_minutes": 24,
                "daily_records": {"2026-07-21": {"answered": 5, "correct": 3, "time_minutes": 24}},
            },
            "processed_answer_ids": [],
        },
    )
    service = BehaviorService(_Session(user))

    report = await service.get_learning_report(user.id, days=7, now=datetime(2026, 7, 21, tzinfo=timezone.utc))

    assert report["overview"] == {"total_answered": 5, "correct_rate": 0.6, "study_days": 1, "total_time_minutes": 24.0}
    assert report["weak_points"][0]["point"] == "薄弱点"
    assert report["daily_trend"][-1] == {"date": "2026-07-21", "answered": 5, "correct": 3}
    assert len(report["daily_trend"]) == 7
