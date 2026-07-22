import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class _StatsSession:
    def __init__(self, owner_id):
        now = datetime.now(timezone.utc)
        self.results = [
            _ScalarResult(SimpleNamespace(
                user_id=owner_id,
                started_at=now,
                completed_at=now,
                status="completed",
                total_questions=3,
                correct_count=2,
            )),
            _ScalarResult(45),
        ]

    async def execute(self, _statement):
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_session_stats_match_public_response_schema():
    from app.schemas.learning import SessionStats
    from app.services.learning_service import get_session_stats

    owner_id = uuid.uuid4()
    stats = await get_session_stats(_StatsSession(owner_id), uuid.uuid4(), owner_id)

    validated = SessionStats(**stats)
    assert validated.accuracy_rate == 66
    assert validated.total_time_seconds == 45
