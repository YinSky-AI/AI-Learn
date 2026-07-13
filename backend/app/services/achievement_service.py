# -*- coding: utf-8 -*-
"""
成就服务
处理成就查询、检查和发放
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement import Achievement, UserAchievement
from app.models.user import User
from app.models.learning import LearningSession


async def get_all_achievements(db: AsyncSession) -> List[Achievement]:
    """获取所有成就列表"""
    stmt = select(Achievement).order_by(Achievement.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_user_achievements(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> List[dict]:
    """
    获取用户已解锁的成就列表（含是否已解锁标记）
    """
    # 所有成就
    all_stmt = select(Achievement).order_by(Achievement.created_at)
    all_result = await db.execute(all_stmt)
    all_achievements = list(all_result.scalars().all())

    # 用户已解锁的成就 ID
    unlocked_stmt = select(UserAchievement.achievement_id).where(
        UserAchievement.user_id == user_id
    )
    unlocked_result = await db.execute(unlocked_stmt)
    unlocked_ids = {row[0] for row in unlocked_result.all()}

    # 组合结果
    result = []
    for ach in all_achievements:
        unlocked = ach.id in unlocked_ids
        result.append({
            "id": ach.id,
            "code": ach.code,
            "name": ach.name,
            "description": ach.description,
            "icon_url": ach.icon_url,
            "is_unlocked": unlocked,
        })

    return result


async def check_and_award_achievements(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> List[UserAchievement]:
    """
    检查用户是否满足成就条件，满足则自动发放
    返回新发放的成就列表
    """
    # 获取用户信息
    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if user is None:
        return []

    # 获取所有成就
    ach_stmt = select(Achievement)
    ach_result = await db.execute(ach_stmt)
    achievements = list(ach_result.scalars().all())

    # 获取已解锁的成就
    unlocked_stmt = select(UserAchievement.achievement_id).where(
        UserAchievement.user_id == user_id
    )
    unlocked_result = await db.execute(unlocked_stmt)
    unlocked_ids = {row[0] for row in unlocked_result.all()}

    # 获取会话统计
    session_stmt = select(func.count()).where(
        LearningSession.user_id == user_id,
        LearningSession.status == "completed",
    )
    completed_sessions = (await db.execute(session_stmt)).scalar() or 0

    newly_awarded = []

    for ach in achievements:
        if ach.id in unlocked_ids:
            continue

        awarded = False
        criteria = ach.criteria or {}

        if ach.code == "FIRST_LOGIN":
            awarded = True
        elif ach.code == "FIRST_LEARN":
            awarded = completed_sessions >= 1
        elif ach.code == "CORRECT_10":
            awarded = user.total_score >= 100
        elif ach.code == "STREAK_3":
            awarded = user.streak_days >= 3
        elif ach.code == "STREAK_7":
            awarded = user.streak_days >= 7
        elif ach.code == "PERFECT_SCORE":
            awarded = completed_sessions >= 5

        if awarded:
            user_achievement = UserAchievement(
                id=uuid.uuid4(),
                user_id=user_id,
                achievement_id=ach.id,
                achieved_at=datetime.now(timezone.utc),
            )
            db.add(user_achievement)
            newly_awarded.append(user_achievement)

    if newly_awarded:
        await db.flush()

    return newly_awarded


async def get_achievement_by_code(
    db: AsyncSession,
    code: str,
) -> Optional[Achievement]:
    """根据编码获取成就"""
    stmt = select(Achievement).where(Achievement.code == code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
