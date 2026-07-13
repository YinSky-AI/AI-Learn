# -*- coding: utf-8 -*-
"""
进度 API
处理学习进度统计、学科进度、难度分布等
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import ApiResponse, success_response
from app.services import progress_service

router = APIRouter()


@router.get("/overview", response_model=ApiResponse)
async def get_learning_overview(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    获取学习进度总览
    返回总会话数、完成数、答题数、正确率、总用时等
    """
    progress = await progress_service.get_user_learning_progress(db, user_id)
    return success_response(
        data=progress,
        message="获取学习进度总览成功",
    )


@router.get("/subject/{subject_code}", response_model=ApiResponse)
async def get_subject_progress(
    subject_code: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    获取某学科的学习进度
    返回已学知识点数、覆盖率、正确率等
    """
    progress = await progress_service.get_subject_progress(db, user_id, subject_code)
    return success_response(
        data=progress,
        message="获取学科进度成功",
    )


@router.get("/recent", response_model=ApiResponse)
async def get_recent_activity(
    limit: int = Query(default=10, ge=1, le=50, description="最近记录数"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    获取最近学习活动
    """
    sessions = await progress_service.get_recent_sessions(db, user_id, limit=limit)
    return success_response(
        data=[
            {
                "id": str(s.id),
                "knowledge_node_id": str(s.knowledge_node_id),
                "difficulty_level": s.difficulty_level,
                "status": s.status,
                "correct_count": s.correct_count,
                "total_questions": s.total_questions,
                "started_at": str(s.started_at),
                "completed_at": str(s.completed_at) if s.completed_at else None,
            }
            for s in sessions
        ],
        message="获取最近活动成功",
    )


@router.get("/difficulty-distribution", response_model=ApiResponse)
async def get_difficulty_distribution(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    获取各难度的答题分布
    返回各难度级别的答题数、正确数、正确率
    """
    distribution = await progress_service.get_difficulty_distribution(db, user_id)
    return success_response(
        data=distribution,
        message="获取难度分布成功",
    )
