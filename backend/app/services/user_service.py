# -*- coding: utf-8 -*-
"""
用户服务
处理用户信息查询、更新、行为模型管理
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, UserProfileResponse, UserStatsResponse


async def get_user_by_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> User:
    """
    根据 ID 获取用户
    """
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BIZ_001", "message": "用户不存在"},
        )
    return user


async def get_user_by_email(
    db: AsyncSession,
    email: str,
) -> Optional[User]:
    """
    根据邮箱获取用户
    """
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    update_data: UserUpdate,
) -> User:
    """
    更新用户信息
    """
    user = await get_user_by_id(db, user_id)

    # 只更新非 None 字段
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(user, field, value)

    db.add(user)
    await db.flush()
    return user


async def get_user_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> UserProfileResponse:
    """
    获取用户行为档案
    """
    user = await get_user_by_id(db, user_id)
    return UserProfileResponse(
        id=user.id,
        nickname=user.nickname,
        age_group=user.age_group,
        total_score=user.total_score,
        streak_days=user.streak_days,
        behavior_profile=user.behavior_profile,
    )


async def update_behavior_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    profile_data: dict,
) -> User:
    """
    更新用户行为模型
    """
    user = await get_user_by_id(db, user_id)
    user.behavior_profile = profile_data
    db.add(user)
    await db.flush()
    return user


async def update_streak(
    db: AsyncSession,
    user_id: uuid.UUID,
    increment: int = 1,
) -> User:
    """
    更新用户连续学习天数
    """
    user = await get_user_by_id(db, user_id)
    user.streak_days += increment
    if user.streak_days < 0:
        user.streak_days = 0
    db.add(user)
    await db.flush()
    return user


async def add_score(
    db: AsyncSession,
    user_id: uuid.UUID,
    points: int,
) -> User:
    """
    增加用户积分
    """
    user = await get_user_by_id(db, user_id)
    user.total_score += points
    db.add(user)
    await db.flush()
    return user


async def get_user_stats(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> UserStatsResponse:
    """
    获取用户学习统计
    综合统计 LearningSession（AI答题）和 UserLesson（课时完成）数据
    """
    from app.models.learning import Answer, LearningSession
    from app.models.course import UserLesson

    user = await get_user_by_id(db, user_id)

    # ===== 学习时间统计（从 UserLesson 表） =====
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # 今日学习分钟数
    stmt = (
        select(func.coalesce(func.sum(UserLesson.time_spent_seconds), 0))
        .where(
            UserLesson.user_id == str(user_id),
            UserLesson.completed == True,
            UserLesson.created_at >= today,
        )
    )
    result = await db.execute(stmt)
    today_seconds = result.scalar_one_or_none() or 0
    today_minutes = int(today_seconds / 60)

    # 本周学习小时数
    week_start = today - timedelta(days=today.weekday())
    stmt = (
        select(func.coalesce(func.sum(UserLesson.time_spent_seconds), 0))
        .where(
            UserLesson.user_id == str(user_id),
            UserLesson.completed == True,
            UserLesson.created_at >= week_start,
        )
    )
    result = await db.execute(stmt)
    week_seconds = result.scalar_one_or_none() or 0
    week_hours = round(week_seconds / 3600, 1)

    # ===== 课时完成统计（从 UserLesson 表） =====
    # 已完成课时数
    stmt = select(func.count(UserLesson.id)).where(
        UserLesson.user_id == str(user_id),
        UserLesson.completed == True,
    )
    result = await db.execute(stmt)
    completed_lessons = result.scalar_one_or_none() or 0

    # ===== 课程完成统计（从 UserCourse 表，更可靠） =====
    from app.models.course import UserCourse
    stmt = select(func.count(UserCourse.id)).where(
        UserCourse.user_id == str(user_id),
        UserCourse.status == "completed",
    )
    result = await db.execute(stmt)
    completed_courses = result.scalar_one_or_none() or 0

    stmt = select(func.count(UserCourse.id)).where(
        UserCourse.user_id == str(user_id),
        UserCourse.status == "enrolled",
    )
    result = await db.execute(stmt)
    in_progress_courses = result.scalar_one_or_none() or 0

    total_courses = in_progress_courses + completed_courses
    overall_progress = int((completed_courses / total_courses) * 100) if total_courses > 0 else 0

    return UserStatsResponse(
        total_score=user.total_score,
        streak_days=user.streak_days,
        today_study_minutes=today_minutes,
        week_study_hours=week_hours,
        total_completed_lessons=completed_lessons,
        in_progress_courses=in_progress_courses,
        completed_courses=completed_courses,
        overall_progress=overall_progress,
    )
