# -*- coding: utf-8 -*-
"""
学习会话 API 模块

提供学习会话的生命周期管理接口，包括创建会话、提交答案、完成会话、查询统计等。
所有接口均需登录认证，学习数据与当前用户绑定。

主要功能：
    - 创建学习会话（绑定知识点与难度）
    - 提交答案（自动判题并更新会话统计）
    - 完成会话（结算统计数据）
    - 查询会话统计与历史列表
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
    创建学习会话接口

    为当前用户开启一个新的学习会话，绑定知识点与难度等级。

    Args:
        request (LearningSessionCreate): 会话创建请求体（知识点 ID、难度等级）
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[LearningSessionResponse]: 新创建的学习会话信息
    """
    # 调用学习服务创建会话记录
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
    提交答案接口

    在指定学习会话中回答一道题，系统自动判题并更新会话统计（总题数、正确数）。

    Args:
        session_id (uuid.UUID): 学习会话 ID
        request (AnswerSubmit): 答题请求体（题目 ID、用户答案、用时）
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[AnswerResult]: 答题结果（是否正确、标准答案等）

    Raises:
        HTTPException: 会话不存在、已结束或题目不存在时抛出相应错误
    """
    # 调用学习服务完成判题与统计更新
    answer_result = await learning_service.submit_answer(
        db,
        session_id=session_id,
        user_id=user_id,
        question_id=request.question_id,
        answer_id=request.answer_id,
        user_answer=request.user_answer,
        time_spent_seconds=request.time_spent_seconds,
        solution_steps=request.solution_steps,
        confidence=request.confidence,
    )
    return success_response(
        data=AnswerResult.model_validate(answer_result),
        message="答案提交成功",
    )


@router.post("/sessions/{session_id}/complete", response_model=ApiResponse[SessionStats])
async def complete_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    完成学习会话接口

    结束指定学习会话，标记状态为 completed，并返回会话统计数据。

    Args:
        session_id (uuid.UUID): 学习会话 ID
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[SessionStats]: 会话统计（正确数、总题数、正确率、总用时）

    Raises:
        HTTPException: 会话不存在或已结束时抛出相应错误
    """
    # 标记会话完成并结算统计数据
    await learning_service.complete_session(db, session_id, user_id=user_id)
    stats = await learning_service.get_session_stats(db, session_id, user_id=user_id)
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
    """
    获取学习会话统计信息接口

    查询指定学习会话的实时统计数据，包括答题数、正确数、正确率、总用时等。

    Args:
        session_id (uuid.UUID): 学习会话 ID
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[SessionStats]: 会话统计详情
    """
    # 查询会话统计（若未完成则计算当前已用时间）
    stats = await learning_service.get_session_stats(db, session_id, user_id=user_id)
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
    """
    我的学习会话列表接口（分页）

    分页查询当前用户的所有学习会话历史，按开始时间倒序排列。

    Args:
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页学习会话列表
    """
    # 查询用户会话历史
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
