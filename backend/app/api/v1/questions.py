# -*- coding: utf-8 -*-
"""
AI 出题 API 模块

提供基于 AI 的题目生成与管理接口，包括创建生成任务、查询批次与历史、生成变式题等。
所有接口均需登录认证，生成记录与当前用户绑定。

主要功能：
    - 创建 AI 题目生成任务（异步批次）
    - 查询生成批次列表与详情
    - 基于已有题目生成变式题
    - 查询生成题目历史记录
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.ai.provider import get_ai_provider
from app.ai.question_pipeline import QuestionGenerationError, QuestionPipeline
from app.schemas.common import ApiResponse, paged_response, success_response
from app.schemas.question import (
    QuestionGenerateRequest,
    GeneratedQuestionResponse,
    BatchResponse,
    VariantRequest,
    GenerateResultResponse,
)
from app.services import question_generation_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=ApiResponse)
async def generate_questions(
    request: QuestionGenerateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    AI 生成题目接口

    通过独立的两层流水线生成并审核题目，在同一事务中持久化通过的批次。

    Args:
        request (QuestionGenerateRequest): 生成请求体（学科、主题、难度、题型、数量等）
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 包含 batch_id 与任务状态的提交结果
    """
    pipeline = QuestionPipeline(get_ai_provider())
    try:
        batch = await question_generation_service.generate_reviewed_batch(
            db,
            user_id=user_id,
            request=request,
            pipeline=pipeline,
        )
    except QuestionGenerationError as error:
        logger.warning("题目生成未通过审核: %s", error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return success_response(
        data={
            "batch_id": str(batch.id),
            "status": "completed",
        },
        message="题目生成完成",
    )


@router.get("/batches", response_model=ApiResponse)
async def list_batches(
    subject_code: Optional[str] = Query(None, description="学科筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    生成批次列表接口（分页）

    分页查询当前用户的 AI 题目生成批次，支持按学科和状态筛选。

    Args:
        subject_code (Optional[str]): 学科编码筛选
        status (Optional[str]): 批次状态筛选（pending / completed / failed）
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页生成批次列表
    """
    # 查询用户的生成批次记录
    result = await question_generation_service.list_user_batches(
        db,
        user_id=user_id,
        subject_code=subject_code,
        status=status,
        page=page,
        page_size=page_size,
    )
    items = [BatchResponse.model_validate(b) for b in result["items"]]
    return paged_response(
        data=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/batches/{batch_id}", response_model=ApiResponse)
async def get_batch_detail(
    batch_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    生成批次详情接口

    查询指定批次的详细信息以及该批次下所有生成的题目列表。

    Args:
        batch_id (uuid.UUID): 生成批次 ID
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 批次详情 + 生成题目列表
    """
    # 查询批次基本信息
    batch = await question_generation_service.get_batch_by_id(db, batch_id)
    if batch is None:
        return ApiResponse(code="BIZ_001", message="批次不存在", data=None)

    # 查询批次关联的生成题目
    questions = await question_generation_service.get_batch_questions(db, batch_id)
    return success_response(
        data={
            "batch": BatchResponse.model_validate(batch),
            "questions": [GeneratedQuestionResponse.model_validate(q) for q in questions],
        },
        message="获取批次详情成功",
    )


@router.post("/variant", response_model=ApiResponse)
async def generate_variant(
    request: VariantRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    生成变式题接口

    基于已有题目创建变式题生成任务，可指定目标难度（默认与原题相同）。

    Args:
        request (VariantRequest): 变式题请求体（原题 ID、目标难度）
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 变式题生成任务提交结果（含 variant_id）

    Raises:
        HTTPException: 原题目不存在时抛出错误
    """
    # 创建变式题记录（状态为 pending，等待 AI 填充内容）
    variant = await question_generation_service.generate_variant(
        db,
        original_question_id=request.question_id,
        user_id=user_id,
        difficulty_level=request.difficulty_level,
    )

    return success_response(
        data={
            "variant_id": str(variant.id),
            "parent_question_id": str(request.question_id),
            "status": "pending",
            "message": "变式题生成任务已提交",
        },
        message="变式题生成任务已创建",
    )


@router.get("/history", response_model=ApiResponse)
async def question_history(
    subject_code: Optional[str] = Query(None, description="学科"),
    course_topic: Optional[str] = Query(None, description="课程主题"),
    difficulty_level: Optional[str] = Query(None, description="难度"),
    quality_status: Optional[str] = Query(None, description="质量状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    生成题目历史接口（分页）

    分页查询当前用户的 AI 生成题目历史，支持按学科、主题、难度、质量状态筛选。

    Args:
        subject_code (Optional[str]): 学科编码筛选
        course_topic (Optional[str]): 课程主题关键词筛选
        difficulty_level (Optional[str]): 难度等级筛选
        quality_status (Optional[str]): 质量状态筛选（unchecked / passed / failed）
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页生成题目历史列表
    """
    # 查询用户生成的题目历史记录
    result = await question_generation_service.list_generated_questions(
        db,
        user_id=user_id,
        subject_code=subject_code,
        course_topic=course_topic,
        difficulty_level=difficulty_level,
        quality_status=quality_status,
        page=page,
        page_size=page_size,
    )
    items = [GeneratedQuestionResponse.model_validate(q) for q in result["items"]]
    return paged_response(
        data=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )
