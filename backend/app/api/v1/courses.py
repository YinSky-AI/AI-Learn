# -*- coding: utf-8 -*-
"""
课程公开 API
处理课程列表、详情、课时查询（无需认证）
课程详情支持可选认证，已登录用户返回课时完成状态
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id_optional
from app.models.course import UserLesson
from app.schemas.common import ApiResponse, paged_response, success_response
from app.schemas.course import CourseBrief, CourseDetail, LessonBrief
from app.services import course_service

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_courses(
    subject: Optional[str] = Query(None, description="学科"),
    difficulty: Optional[str] = Query(None, description="难度"),
    age_group: Optional[str] = Query(None, description="年龄段"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """课程列表（分页、筛选）"""
    result = await course_service.list_courses(
        db,
        subject=subject,
        difficulty=difficulty,
        age_group=age_group,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    items = [CourseBrief.model_validate(item) for item in result["items"]]
    return paged_response(
        data=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{course_id}", response_model=ApiResponse)
async def get_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """课程详情（支持 UUID 或 slug，已登录用户返回课时完成状态）"""
    course = await course_service.get_course_detail(db, course_id)
    if course is None:
        return ApiResponse(code="BIZ_001", message="课程不存在", data=None)

    data = CourseDetail.model_validate(course)

    # 已登录用户：查询课时完成状态并合并
    if user_id and data.lessons:
        lesson_ids = [str(l.id) for l in data.lessons]
        stmt = select(UserLesson).where(
            UserLesson.user_id == user_id,
            UserLesson.lesson_id.in_(lesson_ids),
            UserLesson.completed == True,
        )
        result = await db.execute(stmt)
        completed_lesson_ids = {str(ul.lesson_id) for ul in result.scalars().all()}

        for lesson in data.lessons:
            lesson.completed = str(lesson.id) in completed_lesson_ids

    return success_response(
        data=data,
        message="获取课程详情成功",
    )


@router.get("/{course_id}/lessons", response_model=ApiResponse)
async def list_lessons(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """课时列表（支持 UUID 或 slug，已登录用户返回完成状态）"""
    lessons = await course_service.get_lessons_by_course(db, course_id)
    data = [LessonBrief.model_validate(lesson) for lesson in lessons]

    if user_id and data:
        lesson_ids = [str(l.id) for l in data]
        stmt = select(UserLesson).where(
            UserLesson.user_id == user_id,
            UserLesson.lesson_id.in_(lesson_ids),
            UserLesson.completed == True,
        )
        result = await db.execute(stmt)
        completed_lesson_ids = {str(ul.lesson_id) for ul in result.scalars().all()}

        for lesson in data:
            lesson.completed = str(lesson.id) in completed_lesson_ids

    return success_response(
        data=data,
        message="获取课时列表成功",
    )
