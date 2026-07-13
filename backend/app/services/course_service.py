# -*- coding: utf-8 -*-
"""
课程服务
处理课程、课时、用户课程关联、AI 对话历史的业务逻辑
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, Lesson, UserCourse, UserLesson, ChatMessage


def _try_uuid(value: str) -> Optional[uuid.UUID]:
    """尝试将字符串解析为 UUID，失败返回 None"""
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


async def _resolve_course_id(db: AsyncSession, course_id: str) -> Optional[str]:
    """将字符串课程标识解析为数据库 UUID（支持 UUID 或 slug）"""
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
    """根据 ID 或 slug 获取课程"""
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
    """
    stmt = select(Course).where(Course.is_active == True)
    count_stmt = select(func.count()).select_from(Course).where(
        Course.is_active == True
    )

    # 条件筛选
    if subject:
        stmt = stmt.where(Course.subject == subject)
        count_stmt = count_stmt.where(Course.subject == subject)
    if difficulty:
        stmt = stmt.where(Course.difficulty == difficulty)
        count_stmt = count_stmt.where(Course.difficulty == difficulty)
    if age_group:
        stmt = stmt.where(Course.age_group == age_group)
        count_stmt = count_stmt.where(Course.age_group == age_group)
    if keyword:
        search_filter = or_(
            Course.title.ilike(f"%{keyword}%"),
            Course.description.ilike(f"%{keyword}%"),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    # 排序
    stmt = stmt.order_by(Course.sort_order, Course.created_at.desc())

    # 总数
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
    """
    resolved = await _resolve_course_id(db, course_id)
    if not resolved:
        return None

    stmt = select(Course).where(Course.id == resolved, Course.is_active == True)
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()

    if course is None:
        return None

    # 显式查询课时列表
    lesson_stmt = (
        select(Lesson)
        .where(Lesson.course_id == resolved, Lesson.is_active == True)
        .order_by(Lesson.order)
    )
    lesson_result = await db.execute(lesson_stmt)
    course.lessons = list(lesson_result.scalars().all())

    return course


async def get_lessons_by_course(
    db: AsyncSession,
    course_id: str,
) -> List[Lesson]:
    """获取某课程下的所有课时（支持 UUID 或 slug）"""
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
    """获取用户课程记录"""
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
    """
    if not user_id:
        return None

    resolved = await _resolve_course_id(db, course_id)
    if not resolved:
        raise ValueError("课程不存在")

    user_course = await get_user_course(db, user_id, resolved)
    if user_course is not None:
        # 更新最近访问时间
        user_course.last_accessed_at = datetime.utcnow()
        await db.flush()
        return user_course

    # 创建新记录
    user_course = UserCourse(
        user_id=user_id,
        course_id=resolved,
        progress=0,
        completed_lessons=0,
        status="enrolled",
    )
    db.add(user_course)

    # 增加课程报名人次
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
        # 查询实际已完成的课时数
        completed_stmt = select(func.count()).select_from(UserLesson).where(
            UserLesson.user_id == user_id,
            UserLesson.course_id == resolved,
            UserLesson.completed == True,
        )
        completed_count = (await db.execute(completed_stmt)).scalar() or 0
        user_course.completed_lessons = completed_count
        user_course.progress = min(int(completed_count * 100 / total_lessons), 100)

    # 如果进度达到 100%，更新状态为 completed
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

    # 加载关联的课程信息
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
    """获取用户课时记录"""
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
    标记课时完成，更新 UserLesson + 重新计算 UserCourse 进度
    """
    if not user_id:
        return None

    lesson_uid = _try_uuid(lesson_id)
    if not lesson_uid:
        raise ValueError("课时不存在")

    # 获取课时信息
    lesson_stmt = select(Lesson).where(Lesson.id == str(lesson_uid))
    lesson_result = await db.execute(lesson_stmt)
    lesson = lesson_result.scalar_one_or_none()
    if lesson is None:
        raise ValueError("课时不存在")

    course_id = lesson.course_id

    # 获取或创建用户课时记录
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
    else:
        if not user_lesson.completed:
            user_lesson.completed = True
        user_lesson.time_spent_seconds = user_lesson.time_spent_seconds + time_spent_seconds

    await db.flush()

    # 更新课程进度
    await get_or_create_user_course(db, user_id, course_id)
    await update_course_progress(db, user_id, course_id)

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
    """
    resolved_course = None
    if course_id:
        resolved_course = await _resolve_course_id(db, course_id)

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
    """
    if not user_id:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    conditions = [ChatMessage.user_id == user_id]

    if course_id is not None:
        resolved = await _resolve_course_id(db, course_id)
        if resolved:
            conditions.append(ChatMessage.course_id == resolved)
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
