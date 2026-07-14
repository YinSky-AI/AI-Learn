# -*- coding: utf-8 -*-
"""
学习进度 API 模块

提供用户学习进度的多维度统计接口，包括总览、学科进度、最近活动、难度分布等。
所有接口均需登录认证，数据与当前用户绑定。

主要功能：
    - 学习进度总览（会话数、答题数、正确率、总用时）
    - 某学科的学习进度（知识点覆盖率、正确率）
    - 最近学习活动记录
    - 各难度级别的答题分布与正确率
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
    学习进度总览接口

    聚合返回当前用户的学习核心指标：总会话数、已完成会话数、总答题数、正确率、总学习用时。

    Args:
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 学习进度总览数据
    """
    # 从进度服务聚合用户学习数据
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
    某学科学习进度接口

    返回当前用户在指定学科下的学习数据：已学知识点数、知识点覆盖率、答题正确率。

    Args:
        subject_code (str): 学科编码
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 学科进度详情（覆盖率、正确率等）
    """
    # 查询指定学科的学习进度统计
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
    最近学习活动接口

    返回当前用户最近的学习会话记录，默认 10 条，最大 50 条。

    Args:
        limit (int): 返回记录数限制
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 最近学习活动列表
    """
    # 查询最近的学习会话并按开始时间倒序排列
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
    难度分布统计接口

    返回当前用户在各难度级别下的答题分布：答题总数、正确数、正确率。

    Args:
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 各难度的答题分布统计
    """
    # 按难度级别分组聚合答题数据
    distribution = await progress_service.get_difficulty_distribution(db, user_id)
    return success_response(
        data=distribution,
        message="获取难度分布成功",
    )
