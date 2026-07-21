# -*- coding: utf-8 -*-
"""服务端游戏化奖励：答题事件、等级、打卡与成就。"""

from datetime import date, datetime, timezone
from math import pow

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement import Achievement, UserAchievement
from app.models.gamification import GamificationEvent


ACHIEVEMENTS = (
    ("FIRST_ANSWER", "初出茅庐", "完成第一道题", "🎉", "total_answered", 1),
    ("CORRECT_10", "小试牛刀", "累计答对 10 道题", "✅", "correct_answered", 10),
    ("CORRECT_STREAK_5", "势如破竹", "连续答对 5 道题", "🔥", "max_correct_streak", 5),
    ("CORRECT_STREAK_10", "百战百胜", "连续答对 10 道题", "🏆", "max_correct_streak", 10),
    ("LEVEL_5", "学有所成", "达到 5 级", "🌟", "level", 5),
    ("STUDY_7_DAYS", "一周坚持", "累计学习 7 天", "📅", "study_days_count", 7),
)


def get_level_up_points(level: int) -> int:
    return int(100 * pow(1.2, level - 1))


def calculate_level(total_score: int) -> int:
    level, threshold = 1, 0
    while total_score >= threshold + get_level_up_points(level):
        threshold += get_level_up_points(level)
        level += 1
    return level


def get_level_progress(total_score: int) -> tuple[int, int, int]:
    level, threshold = 1, 0
    while total_score >= threshold + get_level_up_points(level):
        threshold += get_level_up_points(level)
        level += 1
    return level, total_score - threshold, get_level_up_points(level)


def apply_answer_reward(user, *, is_correct: bool, difficulty: str, today: date | None = None) -> dict:
    """只根据服务端判题结果更新用户统计；调用方必须在同一事务中持久化。"""
    today = today or date.today()
    previous_level = calculate_level(user.total_score or 0)
    last_active_date = user.last_active_date
    is_new_day = last_active_date != today
    if is_new_day:
        user.study_days_count = (user.study_days_count or 0) + 1
        user.streak_days = (user.streak_days or 0) + 1 if last_active_date == date.fromordinal(today.toordinal() - 1) else 1
        user.last_active_date = today

    user.total_answered = (user.total_answered or 0) + 1
    normalized_difficulty = {"diff_easy": "beginner", "diff_medium": "intermediate", "diff_hard": "advanced"}.get((difficulty or "").lower(), (difficulty or "").lower())
    base_points = {"beginner": 5, "intermediate": 10, "advanced": 20}.get(normalized_difficulty, 10)
    points_earned = streak_bonus = 0
    if is_correct:
        user.current_correct_streak = (user.current_correct_streak or 0) + 1
        user.max_correct_streak = max(user.max_correct_streak or 0, user.current_correct_streak)
        user.correct_answered = (user.correct_answered or 0) + 1
        streak_bonus = int(base_points * min(user.current_correct_streak * 0.1, 0.5))
        points_earned = base_points + streak_bonus
        user.total_score = (user.total_score or 0) + points_earned
    else:
        user.current_correct_streak = 0

    level = calculate_level(user.total_score or 0)
    return {
        "points_earned": points_earned,
        "base_points": base_points if is_correct else 0,
        "streak_bonus": streak_bonus,
        "total_points": user.total_score or 0,
        "level": level,
        "streak": user.current_correct_streak or 0,
        "leveled_up": level > previous_level,
        "is_new_day": is_new_day,
    }


async def _ensure_achievements(db: AsyncSession) -> list[Achievement]:
    result = await db.execute(select(Achievement))
    existing = {achievement.code: achievement for achievement in result.scalars()}
    for code, name, description, icon, field, minimum in ACHIEVEMENTS:
        if code not in existing:
            achievement = Achievement(code=code, name=name, description=description, icon_url=icon, criteria={"field": field, "minimum": minimum})
            db.add(achievement)
            existing[code] = achievement
    await db.flush()
    return [existing[code] for code, *_ in ACHIEVEMENTS]


async def _award_new_achievements(db: AsyncSession, user) -> list[dict]:
    achievements = await _ensure_achievements(db)
    result = await db.execute(select(UserAchievement.achievement_id).where(UserAchievement.user_id == user.id))
    awarded_ids = {row[0] for row in result}
    newly_awarded = []
    for achievement in achievements:
        criteria = achievement.criteria or {}
        if achievement.id in awarded_ids or (getattr(user, criteria["field"], 0) or 0) < criteria["minimum"]:
            continue
        db.add(UserAchievement(user_id=user.id, achievement_id=achievement.id, achieved_at=datetime.now(timezone.utc)))
        newly_awarded.append({"id": achievement.code, "name": achievement.name, "description": achievement.description, "icon": achievement.icon_url or "🏅"})
    await db.flush()
    return newly_awarded


async def reward_answer_event(db: AsyncSession, *, user, answer, difficulty: str) -> dict:
    """为新 Answer 创建唯一奖励事件；重复 answer_id 只读取既有事件，不二次发奖。"""
    existing = (await db.execute(select(GamificationEvent).where(GamificationEvent.answer_id == answer.id))).scalar_one_or_none()
    if existing:
        return event_to_payload(existing)
    payload = apply_answer_reward(user, is_correct=answer.is_correct, difficulty=difficulty)
    new_achievements = await _award_new_achievements(db, user)
    payload["new_achievements"] = new_achievements
    event = GamificationEvent(answer_id=answer.id, user_id=user.id, points_earned=payload["points_earned"], base_points=payload["base_points"], streak_bonus=payload["streak_bonus"], level=payload["level"], correct_streak=payload["streak"], new_achievements=new_achievements)
    db.add(event)
    await db.flush()
    return payload


def event_to_payload(event: GamificationEvent) -> dict:
    return {"points_earned": event.points_earned, "base_points": event.base_points, "streak_bonus": event.streak_bonus, "level": event.level, "streak": event.correct_streak, "new_achievements": event.new_achievements or [], "replayed": True}


async def get_gamification_summary(db: AsyncSession, user) -> dict:
    level, current_points, points_to_next_level = get_level_progress(user.total_score or 0)
    achievements = await _ensure_achievements(db)
    unlocked = {row[0] for row in (await db.execute(select(UserAchievement.achievement_id).where(UserAchievement.user_id == user.id)))}
    return {
        "total_points": user.total_score or 0,
        "level": level,
        "current_level_points": current_points,
        "points_to_next_level": points_to_next_level,
        "streak_days": user.streak_days or 0,
        "correct_streak": user.current_correct_streak or 0,
        "max_correct_streak": user.max_correct_streak or 0,
        "total_answered": user.total_answered or 0,
        "correct_answered": user.correct_answered or 0,
        "study_days_count": user.study_days_count or 0,
        "achievements": [
            {"id": item.code, "name": item.name, "description": item.description, "icon": item.icon_url or "🏅", "is_unlocked": item.id in unlocked}
            for item in achievements
        ],
    }
