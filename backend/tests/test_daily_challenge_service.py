import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def test_speed_score_rewards_correct_answers_finished_early():
    from app.services.daily_challenge_service import calculate_challenge_score

    fast = calculate_challenge_score(correct_count=4, total_count=5, elapsed_seconds=60, time_limit_seconds=300)
    slow = calculate_challenge_score(correct_count=4, total_count=5, elapsed_seconds=300, time_limit_seconds=300)

    assert fast["score"] > slow["score"]
    assert fast["base_score"] == 400
    assert slow["speed_bonus"] == 0


def test_elapsed_time_is_taken_from_server_start_and_capped_at_limit():
    from app.services.daily_challenge_service import server_elapsed_seconds

    started = datetime.now(timezone.utc) - timedelta(seconds=999)
    assert server_elapsed_seconds(started, time_limit_seconds=300) == 300


def test_score_includes_a_bounded_learning_streak_bonus():
    from app.services.daily_challenge_service import calculate_challenge_score

    without_streak = calculate_challenge_score(
        correct_count=4,
        total_count=5,
        elapsed_seconds=120,
        time_limit_seconds=300,
        streak_days=0,
    )
    long_streak = calculate_challenge_score(
        correct_count=4,
        total_count=5,
        elapsed_seconds=120,
        time_limit_seconds=300,
        streak_days=99,
    )

    assert long_streak["streak_bonus"] == 70
    assert long_streak["score"] == without_streak["score"] + 70


def test_multiple_choice_scoring_is_order_independent():
    from app.services.daily_challenge_service import is_answer_correct

    assert is_answer_correct("MULTIPLE_CHOICE", "A, C", "c,a") is True
    assert is_answer_correct("MULTIPLE_CHOICE", "A, C", "A,B") is False


def test_question_payload_never_exposes_answer_or_explanation():
    from app.services.daily_challenge_service import DailyChallengeService

    payload = DailyChallengeService._question_payload(
        SimpleNamespace(position=1),
        SimpleNamespace(
            id=uuid.uuid4(),
            question_body="1 + 1 = ?",
            question_type="CHOICE",
            options=[{"key": "A", "value": "2"}],
            difficulty_level="DIFF_EASY",
            correct_answer="A",
            explanation="因为 1 + 1 = 2",
        ),
    )

    assert "correct_answer" not in payload
    assert "explanation" not in payload
    assert payload["options"] == [{"key": "A", "value": "2"}]


def test_attempt_payload_exposes_server_calculated_remaining_time():
    from app.services.daily_challenge_service import DailyChallengeService

    challenge = _challenge(time_limit_seconds=300)
    attempt = SimpleNamespace(
        started_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        completed=False,
    )

    payload = DailyChallengeService._attempt_payload(challenge, attempt)

    assert payload["remaining_seconds"] in {179, 180}


def test_timeout_submission_schema_allows_unanswered_questions_for_server_finalization():
    from app.api.v1.daily_challenge import ChallengeSubmitRequest

    request = ChallengeSubmitRequest(
        event_id=uuid.uuid4(),
        answers=[{"question_id": uuid.uuid4(), "selected_answer": ""}],
    )

    assert request.answers[0].selected_answer == ""


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
        self.statements = []
        self.flush_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return _ScalarResult(self.records.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1


def _challenge(**overrides):
    values = {
        "id": uuid.uuid4(),
        "challenge_date": date.today(),
        "subject": "综合",
        "question_count": 1,
        "time_limit_seconds": 300,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_expired_submission_finishes_attempt_once_without_awarding_points(monkeypatch):
    from app.services.daily_challenge_service import DailyChallengeService

    challenge = _challenge(question_count=5)
    attempt = SimpleNamespace(
        id=uuid.uuid4(),
        challenge_id=challenge.id,
        user_id=uuid.uuid4(),
        score=0,
        correct_count=0,
        total_count=0,
        time_spent_seconds=0,
        completed=False,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=301),
        completed_at=None,
    )
    user = SimpleNamespace(id=attempt.user_id, total_score=40, streak_days=2)
    db = _FakeSession(attempt, None)
    service = DailyChallengeService(db)

    async def fake_today():
        return challenge

    async def fake_rank(_attempt):
        return 1

    monkeypatch.setattr(service, "_today", fake_today)
    monkeypatch.setattr(service, "_rank", fake_rank)

    result = await service.submit(user, uuid.uuid4(), [])

    assert result["completed"] is True
    assert result["expired"] is True
    assert result["score"] == 0
    assert result["rank"] == 1
    assert attempt.total_count == 5
    assert user.total_score == 40
    assert db.added == []
    assert db.flush_count == 1


@pytest.mark.asyncio
async def test_completed_attempt_is_an_idempotent_replay_without_side_effects(monkeypatch):
    from app.services.daily_challenge_service import DailyChallengeService

    challenge = _challenge()
    attempt = SimpleNamespace(
        id=uuid.uuid4(),
        challenge_id=challenge.id,
        user_id=uuid.uuid4(),
        score=145,
        correct_count=1,
        total_count=1,
        time_spent_seconds=25,
        completed=True,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=25),
        completed_at=datetime.now(timezone.utc),
    )
    user = SimpleNamespace(id=attempt.user_id, total_score=145, streak_days=0)
    db = _FakeSession(attempt)
    service = DailyChallengeService(db)

    async def fake_today():
        return challenge

    async def fake_rank(_attempt):
        return 1

    monkeypatch.setattr(service, "_today", fake_today)
    monkeypatch.setattr(service, "_rank", fake_rank)

    result = await service.submit(
        user,
        uuid.uuid4(),
        [{"question_id": uuid.uuid4(), "selected_answer": "A"}],
    )

    assert result["replayed"] is True
    assert result["rank"] == 1
    assert result["base_score"] == 100
    assert result["bonus_score"] == 45
    assert user.total_score == 145
    assert db.added == []
    assert db.flush_count == 0

    statement_sql = str(
        db.statements[0].compile(
            dialect=__import__(
                "sqlalchemy.dialects.postgresql", fromlist=["dialect"]
            ).dialect()
        )
    )
    assert "FOR UPDATE" in statement_sql


@pytest.mark.asyncio
async def test_successful_submission_returns_server_rank_and_score_breakdown(monkeypatch):
    from app.services.daily_challenge_service import DailyChallengeService

    challenge = _challenge()
    question_id = uuid.uuid4()
    attempt = SimpleNamespace(
        id=uuid.uuid4(),
        challenge_id=challenge.id,
        user_id=uuid.uuid4(),
        score=0,
        correct_count=0,
        total_count=0,
        time_spent_seconds=0,
        completed=False,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=30),
        completed_at=None,
    )
    user = SimpleNamespace(id=attempt.user_id, total_score=10, streak_days=3)
    mapping = SimpleNamespace(position=1)
    question = SimpleNamespace(id=question_id, question_type="CHOICE", correct_answer="A")
    db = _FakeSession(attempt, None)
    service = DailyChallengeService(db)

    async def fake_today():
        return challenge

    async def fake_questions(_challenge_id):
        return [(mapping, question)]

    async def fake_rank(_attempt):
        return 4

    monkeypatch.setattr(service, "_today", fake_today)
    monkeypatch.setattr(service, "_questions", fake_questions)
    monkeypatch.setattr(service, "_rank", fake_rank)

    result = await service.submit(
        user,
        uuid.uuid4(),
        [{"question_id": question_id, "selected_answer": "A"}],
    )

    assert result["rank"] == 4
    assert result["base_score"] == 100
    assert result["streak_bonus"] == 30
    assert result["score"] == result["base_score"] + result["speed_bonus"] + result["streak_bonus"]
    assert user.total_score == 10 + result["score"]
    assert db.flush_count == 1
