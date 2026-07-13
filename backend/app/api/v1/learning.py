# -*- coding: utf-8 -*-
"""
学习 API
处理学习会话创建、答题提交、会话完成等
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import ApiResponse, paged_response, success_response
from app.schemas.learning import (
    LearningSessionCreate,
    LearningSessionResponse,
    AnswerSubmit,
    AnswerResult,
    SessionCompleteRequest,
    SessionStats,
)
from app.services import learning_service

router = APIRouter()


@router.post("/sessions", response_model=ApiResponse[LearningSessionResponse])
async def create_session(
    request: LearningSessionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    创建学习会话
    开始学习某个知识点
    """
    session = await learning_service.create_session(
        db,
        user_id=user_id,
        knowledge_node_id=request.knowledge_node_id,
        difficulty_level=request.difficulty_level,
    )
    return success_response(
        data=LearningSessionResponse.model_validate(session),
        message="学习会话创建成功",
    )


@router.post("/sessions/{session_id}/answer", response_model=ApiResponse[AnswerResult])
async def submit_answer(
    session_id: uuid.UUID,
    request: AnswerSubmit,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    提交答案
    在学习会话中回答一道题
    """
    answer = await learning_service.submit_answer(
        db,
        session_id=session_id,
        question_id=request.question_id,
        user_answer=request.user_answer,
        time_spent_seconds=request.time_spent_seconds,
    )
    return success_response(
        data=AnswerResult.model_validate(answer),
        message="答案提交成功",
    )


@router.post("/sessions/{session_id}/complete", response_model=ApiResponse[SessionStats])
async def complete_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    完成学习会话
    结束当前学习会话，返回统计数据
    """
    await learning_service.complete_session(db, session_id)
    stats = await learning_service.get_session_stats(db, session_id)
    return success_response(
        data=SessionStats(**stats),
        message="学习会话已完成",
    )


@router.get("/sessions/{session_id}", response_model=ApiResponse[SessionStats])
async def get_session_stats(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取学习会话统计信息"""
    stats = await learning_service.get_session_stats(db, session_id)
    return success_response(
        data=SessionStats(**stats),
        message="获取会话统计成功",
    )


@router.get("/sessions", response_model=ApiResponse)
async def list_my_sessions(
    page: int = 1,
    page_size: int = 20,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取我的学习会话列表"""
    result = await learning_service.list_user_sessions(
        db, user_id=user_id, page=page, page_size=page_size
    )
    items = [LearningSessionResponse.model_validate(s) for s in result["items"]]
    return paged_response(
        data=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )
