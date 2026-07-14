# -*- coding: utf-8 -*-
"""
用户个人课程 API 模块

提供与当前登录用户相关的课程操作接口，包括我的课程列表、课程报名、课时完成、AI 对话历史。
部分接口支持可选认证，未登录用户会收到明确的提示信息。

主要功能：
    - 我的课程列表（分页查询）
    - 课程报名（自动创建 UserCourse 记录）
    - 课时完成（更新学习进度并累计积分）
    - AI 对话历史查询与保存
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
    """
    我的课程列表接口

    分页查询当前登录用户的课程学习记录，包含报名状态与进度信息。

    Args:
        user_id (Optional[str]): 当前登录用户 ID（可选认证）
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页用户课程列表
    """
    # 查询用户的课程记录（含关联课程信息）
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
    """
    课程报名接口

    为当前登录用户报名指定课程。若已报名则返回已有记录。

    Args:
        course_id (str): 课程 ID（UUID 或 slug）
        user_id (Optional[str]): 当前登录用户 ID（可选认证）
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 报名后的用户课程记录
    """
    # 未登录用户不允许报名
    if user_id is None:
        return ApiResponse(
            code="AUTH_001",
            message="请先登录后再报名课程",
            data=None,
        )

    # 获取或创建用户课程记录，并增加课程报名人次
    user_course = await course_service.get_or_create_user_course(
        db, user_id, course_id
    )
    # 预加载关系属性，避免 MissingGreenlet 错误
    await db.refresh(user_course, ["course"])
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
    """
    完成课时接口

    标记指定课时为已完成，累计学习用时，更新课程总体进度，首次完成时奖励积分。

    Args:
        lesson_id (str): 课时 ID
        body (CompleteLessonRequest): 完成请求体，包含学习用时（秒）
        user_id (Optional[str]): 当前登录用户 ID（可选认证）
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 完成后的用户课时记录
    """
    # 未登录用户不允许完成课时
    if user_id is None:
        return ApiResponse(
            code="AUTH_001",
            message="请先登录后再完成课时",
            data=None,
        )

    # 标记课时完成并触发进度更新与积分奖励
    user_lesson = await course_service.complete_lesson(
        db,
        user_id=user_id,
        lesson_id=lesson_id,
        time_spent_seconds=body.time_spent_seconds,
    )
    # 预加载关系属性，避免 MissingGreenlet 错误
    await db.refresh(user_lesson, ["lesson"])
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
    """
    查询 AI 对话历史接口

    分页获取当前用户与 AI 的聊天记录，支持按课程 ID 或课时 ID 筛选。

    Args:
        course_id (Optional[str]): 课程 ID 筛选
        lesson_id (Optional[str]): 课时 ID 筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 50
        user_id (Optional[str]): 当前登录用户 ID（可选认证）
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页对话消息列表
    """
    # 按条件查询对话历史记录
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
    """
    保存对话消息接口

    保存用户或 AI 助手的一条对话消息到数据库，支持关联课程与课时上下文。

    Args:
        body (ChatMessageCreate): 消息创建请求体（角色、内容、课程/课时 ID、上下文）
        user_id (Optional[str]): 当前登录用户 ID（可选认证）
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 保存后的消息记录
    """
    # 将消息持久化到 ChatMessage 表
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
