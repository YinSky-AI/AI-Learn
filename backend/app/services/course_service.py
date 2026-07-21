# -*- coding: utf-8 -*-
"""
课程服务模块

提供课程、课时、用户课程关联、AI 对话历史等业务逻辑。
支持通过 UUID 或 slug 两种标识访问课程，自动解析并转换为数据库 UUID。

主要功能：
    - 课程查询与列表分页（支持多条件筛选）
    - 课时查询与管理
    - 用户课程报名与进度更新
    - 课时完成与积分奖励
    - AI 对话历史的保存与查询
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, Lesson, UserCourse, UserLesson, ChatMessage


def _try_uuid(value) -> Optional[uuid.UUID]:
    """
    尝试将字符串（或 asyncpg UUID 对象）解析为 UUID

    Args:
        value: 待解析的值（字符串或带 hex 属性的对象）

    Returns:
        Optional[uuid.UUID]: 解析成功返回 UUID 对象，失败返回 None
    """
    try:
        if hasattr(value, 'hex'):
            # asyncpg UUID 对象或其他带 hex 属性的对象
            return uuid.UUID(str(value))
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return None


async def _resolve_course_id(db: AsyncSession, course_id: str) -> Optional[str]:
    """
    将字符串课程标识解析为数据库 UUID（支持 UUID 或 slug）

    解析策略：
        1. 尝试将输入解析为 UUID，若成功则按 UUID 查询
        2. 若 UUID 查询无果或解析失败，则按 slug 查询

    Args:
        db (AsyncSession): 异步数据库会话
        course_id (str): 课程标识（UUID 字符串或 slug）

    Returns:
        Optional[str]: 课程的数据库 UUID 字符串，不存在返回 None
    """
    uid = _try_uuid(course_id)
    if uid:
        # 先按 UUID 查
        stmt = select(Course.id).where(Course.id == str(uid), Course.is_active == True)
        result = await db.execute(stmt)
        found = result.scalar_one_or_none()
        if found:
            return found

    # 再按 slug 查
    stmt = select(Course.id).where(Course.slug == course_id, Course.is_active == True)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ============ Course ============

async def get_course_by_id(
    db: AsyncSession,
    course_id: str,
) -> Optional[Course]:
    """
    根据 ID 或 slug 获取课程

    Args:
        db (AsyncSession): 异步数据库会话
        course_id (str): 课程标识（UUID 或 slug）

    Returns:
        Optional[Course]: 课程对象，不存在返回 None
    """
    resolved = await _resolve_course_id(db, course_id)
    if not resolved:
        return None
    stmt = select(Course).where(Course.id == resolved, Course.is_active == True)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_courses(
    db: AsyncSession,
    subject: Optional[str] = None,
    difficulty: Optional[str] = None,
    age_group: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    分页查询课程列表（支持多条件筛选）

    Args:
        db (AsyncSession): 异步数据库会话
        subject (Optional[str]): 学科编码筛选
        difficulty (Optional[str]): 难度等级筛选
        age_group (Optional[str]): 年龄段编码筛选
        keyword (Optional[str]): 标题或描述关键词搜索
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        dict: 包含 items、total、page、page_size 的分页结果字典
    """
    stmt = select(Course).where(Course.is_active == True)
    count_stmt = select(func.count()).select_from(Course).where(
        Course.is_active == True
    )

    # 条件筛选：学科、难度、年龄段
    if subject:
        stmt = stmt.where(Course.subject == subject)
        count_stmt = count_stmt.where(Course.subject == subject)
    if difficulty:
        stmt = stmt.where(Course.difficulty == difficulty)
        count_stmt = count_stmt.where(Course.difficulty == difficulty)
    if age_group:
        stmt = stmt.where(Course.age_group == age_group)
        count_stmt = count_stmt.where(Course.age_group == age_group)
    # 关键词模糊匹配（标题 + 描述）
    if keyword:
        search_filter = or_(
            Course.title.ilike(f"%{keyword}%"),
            Course.description.ilike(f"%{keyword}%"),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    # 排序：先按 sort_order 再按创建时间倒序
    stmt = stmt.order_by(Course.sort_order, Course.created_at.desc())

    # 查询总数
    total = (await db.execute(count_stmt)).scalar()

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_course_detail(
    db: AsyncSession,
    course_id: str,
) -> Optional[Course]:
    """
    获取课程详情（含课时列表）

    Args:
        db (AsyncSession): 异步数据库会话
        course_id (str): 课程标识（UUID 或 slug）

    Returns:
        Optional[Course]: 课程对象（含 lessons 关联列表），不存在返回 None
    """
    resolved = await _resolve_course_id(db, course_id)
    if not resolved:
        return None

    # 查询课程基本信息
    stmt = select(Course).where(Course.id == resolved, Course.is_active == True)
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()

    if course is None:
        return None

    # 显式查询并绑定课时列表（避免懒加载问题）
    lesson_stmt = (
        select(Lesson)
        .where(Lesson.course_id == resolved, Lesson.is_active == True)
        .order_by(Lesson.order)
    )
    lesson_result = await db.execute(lesson_stmt)
    course.lessons = list(lesson_result.scalars().all())

    return course


async def get_lesson_by_id(
    db: AsyncSession,
    lesson_id: str,
) -> Optional[Lesson]:
    """
    根据 ID 获取课时

    Args:
        db (AsyncSession): 异步数据库会话
        lesson_id (str): 课时 UUID 字符串

    Returns:
        Optional[Lesson]: 课时对象，不存在或格式错误返回 None
    """
    lesson_uid = _try_uuid(lesson_id)
    if not lesson_uid:
        return None

    stmt = select(Lesson).where(Lesson.id == str(lesson_uid), Lesson.is_active == True)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_lessons_by_course(
    db: AsyncSession,
    course_id: str,
) -> List[Lesson]:
    """
    获取某课程下的所有课时（支持 UUID 或 slug）

    Args:
        db (AsyncSession): 异步数据库会话
        course_id (str): 课程标识（UUID 或 slug）

    Returns:
        List[Lesson]: 课时列表，课程不存在时返回空列表
    """
    resolved = await _resolve_course_id(db, course_id)
    if not resolved:
        return []

    stmt = (
        select(Lesson)
        .where(Lesson.course_id == resolved, Lesson.is_active == True)
        .order_by(Lesson.order)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ============ UserCourse ============

async def get_user_course(
    db: AsyncSession,
    user_id: Optional[str],
    course_id: str,
) -> Optional[UserCourse]:
    """
    获取用户课程记录

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 用户 ID
        course_id (str): 课程标识（UUID 或 slug）

    Returns:
        Optional[UserCourse]: 用户课程关联记录，不存在或用户未登录返回 None
    """
    if not user_id:
        return None
    resolved = await _resolve_course_id(db, course_id)
    if not resolved:
        return None

    stmt = select(UserCourse).where(
        UserCourse.user_id == user_id,
        UserCourse.course_id == resolved,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_user_course(
    db: AsyncSession,
    user_id: Optional[str],
    course_id: str,
) -> Optional[UserCourse]:
    """
    获取或创建用户课程记录

    若用户已报名该课程，则更新最近访问时间并返回已有记录；
    否则创建新的报名记录，并增加课程的总报名人次。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 用户 ID
        course_id (str): 课程标识（UUID 或 slug）

    Returns:
        Optional[UserCourse]: 用户课程记录，用户未登录返回 None

    Raises:
        ValueError: 课程不存在时抛出
    """
    if not user_id:
        return None

    resolved = await _resolve_course_id(db, course_id)
    if not resolved:
        raise ValueError("课程不存在")

    # 尝试获取已有记录
    user_course = await get_user_course(db, user_id, resolved)
    if user_course is not None:
        # 更新最近访问时间
        user_course.last_accessed_at = datetime.utcnow()
        await db.flush()
        return user_course

    # 创建新的报名记录
    user_course = UserCourse(
        user_id=user_id,
        course_id=resolved,
        progress=0,
        completed_lessons=0,
        status="enrolled",
    )
    db.add(user_course)

    # 增加课程报名人次统计
    course = await get_course_by_id(db, resolved)
    if course is not None:
        course.enroll_count = course.enroll_count + 1

    await db.flush()
    return user_course


async def update_course_progress(
    db: AsyncSession,
    user_id: Optional[str],
    course_id: str,
) -> Optional[UserCourse]:
    """
    更新课程进度（基于已完成的课时数）

    根据用户实际完成的课时数重新计算课程进度百分比，
    若进度达到 100% 则自动将状态标记为 completed。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 用户 ID
        course_id (str): 课程标识（UUID 或 slug）

    Returns:
        Optional[UserCourse]: 更新后的用户课程记录

    Raises:
        ValueError: 课程或用户课程记录不存在时抛出
    """
    if not user_id:
        return None

    resolved = await _resolve_course_id(db, course_id)
    if not resolved:
        raise ValueError("课程不存在")

    user_course = await get_user_course(db, user_id, resolved)
    if user_course is None:
        raise ValueError("用户课程记录不存在")

    # 获取课程总课时数
    course = await get_course_by_id(db, resolved)
    if course is None:
        raise ValueError("课程不存在")

    total_lessons = course.total_lessons or 0
    if total_lessons == 0:
        user_course.progress = 0
    else:
        # 查询实际已完成的课时数并计算进度百分比
        completed_stmt = select(func.count()).select_from(UserLesson).where(
            UserLesson.user_id == user_id,
            UserLesson.course_id == resolved,
            UserLesson.completed == True,
        )
        completed_count = (await db.execute(completed_stmt)).scalar() or 0
        user_course.completed_lessons = completed_count
        user_course.progress = min(int(completed_count * 100 / total_lessons), 100)

    # 进度达到 100% 时自动标记为已完成
    if user_course.progress >= 100:
        user_course.status = "completed"

    user_course.last_accessed_at = datetime.utcnow()
    await db.flush()
    return user_course


async def get_user_courses(
    db: AsyncSession,
    user_id: Optional[str],
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    获取用户的所有课程

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 用户 ID
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        dict: 分页用户课程列表（含关联课程信息）
    """
    if not user_id:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    stmt = (
        select(UserCourse)
        .where(UserCourse.user_id == user_id)
        .order_by(UserCourse.last_accessed_at.desc())
    )
    count_stmt = select(func.count()).select_from(UserCourse).where(
        UserCourse.user_id == user_id
    )

    total = (await db.execute(count_stmt)).scalar()

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    # 显式加载关联的课程信息（避免懒加载问题）
    for item in items:
        if item.course_id is not None:
            course_stmt = select(Course).where(Course.id == item.course_id)
            course_result = await db.execute(course_stmt)
            item.course = course_result.scalar_one_or_none()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============ UserLesson ============

async def get_user_lesson(
    db: AsyncSession,
    user_id: Optional[str],
    lesson_id: str,
) -> Optional[UserLesson]:
    """
    获取用户课时记录

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 用户 ID
        lesson_id (str): 课时 UUID 字符串

    Returns:
        Optional[UserLesson]: 用户课时记录，不存在或用户未登录返回 None
    """
    if not user_id:
        return None

    lesson_uid = _try_uuid(lesson_id)
    if not lesson_uid:
        return None

    stmt = select(UserLesson).where(
        UserLesson.user_id == user_id,
        UserLesson.lesson_id == str(lesson_uid),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def complete_lesson(
    db: AsyncSession,
    user_id: Optional[str],
    lesson_id: str,
    time_spent_seconds: int = 0,
) -> Optional[UserLesson]:
    """
    标记课时完成，更新 UserLesson 并重新计算 UserCourse 进度

    首次完成课时时，自动为用户增加 10 积分奖励。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 用户 ID
        lesson_id (str): 课时 UUID 字符串
        time_spent_seconds (int): 学习用时（秒），默认 0

    Returns:
        Optional[UserLesson]: 更新后的用户课时记录

    Raises:
        ValueError: 课时不存在或格式错误时抛出
    """
    if not user_id:
        return None

    lesson_uid = _try_uuid(lesson_id)
    if not lesson_uid:
        raise ValueError("课时不存在")

    # 获取课时基本信息（用于确定所属课程）
    lesson_stmt = select(Lesson).where(Lesson.id == str(lesson_uid))
    lesson_result = await db.execute(lesson_stmt)
    lesson = lesson_result.scalar_one_or_none()
    if lesson is None:
        raise ValueError("课时不存在")

    course_id = lesson.course_id

    # 获取或创建用户课时记录
    is_newly_completed = False
    user_lesson = await get_user_lesson(db, user_id, str(lesson_uid))
    if user_lesson is None:
        user_lesson = UserLesson(
            user_id=user_id,
            lesson_id=str(lesson_uid),
            course_id=course_id,
            completed=True,
            time_spent_seconds=time_spent_seconds,
        )
        db.add(user_lesson)
        is_newly_completed = True
    else:
        if not user_lesson.completed:
            user_lesson.completed = True
            is_newly_completed = True
        user_lesson.time_spent_seconds = user_lesson.time_spent_seconds + time_spent_seconds

    await db.flush()

    # 更新课程总体进度
    await get_or_create_user_course(db, user_id, course_id)
    await update_course_progress(db, user_id, course_id)

    # 新完成课时：给用户增加经验值奖励
    if is_newly_completed:
        from app.models.user import User
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if user:
            user.total_score = (user.total_score or 0) + 10

    return user_lesson


# ============ ChatMessage ============

async def save_chat_message(
    db: AsyncSession,
    user_id: Optional[str],
    role: str,
    content: str,
    course_id: Optional[str] = None,
    lesson_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ChatMessage:
    """
    保存 AI 对话消息

    将用户或 AI 的消息持久化到 ChatMessage 表，支持关联课程与课时上下文。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 用户 ID（未登录可为 None）
        role (str): 消息角色（user / assistant / system）
        content (str): 消息内容
        course_id (Optional[str]): 课程标识（UUID 或 slug）
        lesson_id (Optional[str]): 课时 UUID 字符串
        context (Optional[Dict[str, Any]]): 上下文信息字典

    Returns:
        ChatMessage: 保存后的消息 ORM 对象
    """
    # 解析课程 ID（支持 UUID 或 slug）
    resolved_course = None
    if course_id:
        resolved_course = await _resolve_course_id(db, course_id)

    # 解析课时 ID
    resolved_lesson = None
    if lesson_id:
        lid = _try_uuid(lesson_id)
        if lid:
            resolved_lesson = str(lid)

    message = ChatMessage(
        user_id=user_id,
        role=role,
        content=content,
        course_id=resolved_course,
        lesson_id=resolved_lesson,
        context=context,
    )
    db.add(message)
    await db.flush()
    return message


async def get_chat_history(
    db: AsyncSession,
    user_id: Optional[str],
    course_id: Optional[str] = None,
    lesson_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    获取某用户的对话历史

    支持按课程 ID 或课时 ID 筛选，默认按创建时间倒序排列。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 用户 ID
        course_id (Optional[str]): 课程标识（UUID 或 slug）
        lesson_id (Optional[str]): 课时 UUID 字符串
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 50

    Returns:
        dict: 分页对话历史记录
    """
    if not user_id:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    conditions = [ChatMessage.user_id == user_id]

    # 按课程 ID 筛选（自动解析 UUID / slug）
    if course_id is not None:
        resolved = await _resolve_course_id(db, course_id)
        if resolved:
            conditions.append(ChatMessage.course_id == resolved)
    # 按课时 ID 筛选
    if lesson_id is not None:
        lid = _try_uuid(lesson_id)
        if lid:
            conditions.append(ChatMessage.lesson_id == str(lid))

    stmt = select(ChatMessage).where(and_(*conditions)).order_by(ChatMessage.created_at.desc())
    count_stmt = select(func.count()).select_from(ChatMessage).where(and_(*conditions))

    total = (await db.execute(count_stmt)).scalar()

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
