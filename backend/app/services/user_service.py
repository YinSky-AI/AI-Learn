# -*- coding: utf-8 -*-
"""
用户服务模块

提供用户信息管理、行为档案、学习统计等核心业务逻辑。
所有函数均通过异步数据库会话操作，返回 ORM 对象或 Pydantic 响应模型。

主要功能：
    - 用户查询（按 ID、按邮箱）
    - 用户信息更新（部分字段更新）
    - 行为档案查询与更新
    - 连续学习天数与积分管理
    - 学习统计数据聚合（多表查询）
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

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID

    Returns:
        User: 用户 ORM 对象

    Raises:
        HTTPException: 用户不存在或已删除时抛出 404
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

    Args:
        db (AsyncSession): 异步数据库会话
        email (str): 用户邮箱

    Returns:
        Optional[User]: 用户对象，不存在则返回 None
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

    采用部分更新策略，仅更新请求体中提供的非 None 字段。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        update_data (UserUpdate): 更新数据

    Returns:
        User: 更新后的用户对象
    """
    user = await get_user_by_id(db, user_id)

    # 只更新非 None 字段（exclude_unset=True 确保仅设置请求中显式传入的字段）
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

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID

    Returns:
        UserProfileResponse: 用户行为档案响应模型
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

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        profile_data (dict): 新的行为模型数据（JSON 格式）

    Returns:
        User: 更新后的用户对象
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

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        increment (int): 增量（正数为增加，负数为减少），默认 1

    Returns:
        User: 更新后的用户对象
    """
    user = await get_user_by_id(db, user_id)
    user.streak_days += increment
    # 确保连续天数不为负数
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

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        points (int): 增加的积分数（可为负数表示扣减）

    Returns:
        User: 更新后的用户对象
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

    综合聚合 LearningSession（AI 答题）和 UserLesson（课时完成）等多表数据，
    返回用户的学习时长、课时完成数、课程进度等核心指标。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID

    Returns:
        UserStatsResponse: 用户学习统计响应模型
    """
    from app.models.learning import Answer, LearningSession
    from app.models.course import UserLesson

    user = await get_user_by_id(db, user_id)

    # ===== 学习时间统计（从 UserLesson 表聚合） =====
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

    # 计算总体课程完成进度百分比
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
