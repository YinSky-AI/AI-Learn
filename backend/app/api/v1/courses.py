# -*- coding: utf-8 -*-
"""
课程公开 API
处理课程列表、详情、课时查询（无需认证）
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
):
    """课程详情（支持 UUID 或 slug）"""
    course = await course_service.get_course_detail(db, course_id)
    if course is None:
        return ApiResponse(code="BIZ_001", message="课程不存在", data=None)
    return success_response(
        data=CourseDetail.model_validate(course),
        message="获取课程详情成功",
    )


@router.get("/{course_id}/lessons", response_model=ApiResponse)
async def list_lessons(
    course_id: str,
    db: AsyncSession = Depends(get_db),
):
    """课时列表（支持 UUID 或 slug）"""
    lessons = await course_service.get_lessons_by_course(db, course_id)
    return success_response(
        data=[LessonBrief.model_validate(lesson) for lesson in lessons],
        message="获取课时列表成功",
    )
