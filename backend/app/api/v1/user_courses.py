# -*- coding: utf-8 -*-
"""
用户个人课程 API
处理我的课程、报名、完成课时、AI 对话历史（可选认证）
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id_optional
from app.schemas.common import ApiResponse, paged_response, success_response
from app.schemas.course import (
    ChatMessageCreate,
    ChatMessageResponse,
    UserCourseResponse,
    UserLessonResponse,
)
from app.services import course_service

router = APIRouter()


# ============ 我的课程 ============

@router.get("/courses", response_model=ApiResponse)
async def get_my_courses(
    user_id: Optional[str] = Depends(get_current_user_id_optional),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """我的课程列表"""
    result = await course_service.get_user_courses(
        db,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    items = [UserCourseResponse.model_validate(item) for item in result["items"]]
    return paged_response(
        data=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.post("/courses/{course_id}/enroll", response_model=ApiResponse)
async def enroll_course(
    course_id: str,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """报名课程"""
    if user_id is None:
        return ApiResponse(
            code="AUTH_001",
            message="请先登录后再报名课程",
            data=None,
        )

    user_course = await course_service.get_or_create_user_course(
        db, user_id, course_id
    )
    return success_response(
        data=UserCourseResponse.model_validate(user_course),
        message="报名成功",
    )


# ============ 课时完成 ============

class CompleteLessonRequest(BaseModel):
    """完成课时请求"""
    time_spent_seconds: int = Field(default=0, ge=0, description="学习用时（秒）")


@router.post("/lessons/{lesson_id}/complete", response_model=ApiResponse)
async def complete_lesson(
    lesson_id: str,
    body: CompleteLessonRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """完成课时"""
    if user_id is None:
        return ApiResponse(
            code="AUTH_001",
            message="请先登录后再完成课时",
            data=None,
        )

    user_lesson = await course_service.complete_lesson(
        db,
        user_id=user_id,
        lesson_id=lesson_id,
        time_spent_seconds=body.time_spent_seconds,
    )
    return success_response(
        data=UserLessonResponse.model_validate(user_lesson),
        message="课时完成",
    )


# ============ AI 对话历史 ============

@router.get("/chat", response_model=ApiResponse)
async def get_chat_history(
    course_id: Optional[str] = Query(None, description="课程 ID"),
    lesson_id: Optional[str] = Query(None, description="课时 ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量"),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """对话历史（按 course_id 筛选）"""
    result = await course_service.get_chat_history(
        db,
        user_id=user_id,
        course_id=course_id,
        lesson_id=lesson_id,
        page=page,
        page_size=page_size,
    )
    items = [ChatMessageResponse.model_validate(item) for item in result["items"]]
    return paged_response(
        data=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.post("/chat", response_model=ApiResponse)
async def save_chat_message(
    body: ChatMessageCreate,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """保存对话消息"""
    message = await course_service.save_chat_message(
        db,
        user_id=user_id,
        role=body.role,
        content=body.content,
        course_id=body.course_id,
        lesson_id=body.lesson_id,
        context=body.context,
    )
    return success_response(
        data=ChatMessageResponse.model_validate(message),
        message="消息保存成功",
    )
