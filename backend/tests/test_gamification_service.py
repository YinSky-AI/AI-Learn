from datetime import date, timedelta
from types import SimpleNamespace

from app.services.gamification_service import apply_answer_reward, calculate_level


def _user(**overrides):
    values = {
        "total_score": 0,
        "streak_days": 0,
        "current_correct_streak": 0,
        "max_correct_streak": 0,
        "total_answered": 0,
        "correct_answered": 0,
        "last_active_date": None,
        "study_days_count": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_correct_answer_awards_server_side_points_and_updates_streak():
    user = _user()

    reward = apply_answer_reward(user, is_correct=True, difficulty="advanced", today=date(2026, 7, 21))

    assert reward["points_earned"] == 22
    assert reward["base_points"] == 20
    assert reward["streak_bonus"] == 2
    assert user.total_score == 22
    assert user.current_correct_streak == 1
    assert user.max_correct_streak == 1
    assert user.total_answered == 1
    assert user.correct_answered == 1
    assert user.streak_days == 1
    assert user.study_days_count == 1


def test_incorrect_answer_resets_correct_streak_without_deducting_score():
    user = _user(total_score=30, current_correct_streak=4, max_correct_streak=4)

    reward = apply_answer_reward(user, is_correct=False, difficulty="beginner", today=date(2026, 7, 21))

    assert reward["points_earned"] == 0
    assert user.total_score == 30
    assert user.current_correct_streak == 0
    assert user.max_correct_streak == 4
    assert user.total_answered == 1
    assert user.correct_answered == 0


def test_daily_streak_increments_once_per_consecutive_day_and_resets_after_gap():
    user = _user(last_active_date=date(2026, 7, 20), streak_days=3, study_days_count=3)

    apply_answer_reward(user, is_correct=True, difficulty="beginner", today=date(2026, 7, 21))
    assert (user.streak_days, user.study_days_count) == (4, 4)

    apply_answer_reward(user, is_correct=True, difficulty="beginner", today=date(2026, 7, 21))
    assert (user.streak_days, user.study_days_count) == (4, 4)

    user.last_active_date = date(2026, 7, 18)
    apply_answer_reward(user, is_correct=True, difficulty="beginner", today=date(2026, 7, 21))
    assert user.streak_days == 1
    assert user.study_days_count == 5


def test_level_uses_cumulative_thresholds():
    assert calculate_level(0) == 1
    assert calculate_level(100) == 2
    assert calculate_level(219) == 2
    assert calculate_level(220) == 3
