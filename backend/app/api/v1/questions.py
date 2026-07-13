# -*- coding: utf-8 -*-
"""
AI 出题 API
处理题目生成、批次查询、变式题生成、历史查询
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
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


@router.post("/generate", response_model=ApiResponse)
async def generate_questions(
    request: QuestionGenerateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    AI 生成题目
    根据学科、主题、难度等参数生成练习题
    """
    # 创建生成批次
    batch = await question_generation_service.create_generation_batch(
        db, user_id=user_id, request=request
    )

    # TODO: 调用 AI Harness 执行实际生成
    # 目前返回批次信息，实际生成为异步流程
    return success_response(
        data={
            "batch_id": str(batch.id),
            "status": batch.status,
            "message": "题目生成任务已提交，请稍后查询结果",
        },
        message="题目生成任务已创建",
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
    查询生成批次列表
    """
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
    获取批次详情（含生成的题目列表）
    """
    batch = await question_generation_service.get_batch_by_id(db, batch_id)
    if batch is None:
        return ApiResponse(code="BIZ_001", message="批次不存在", data=None)

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
    生成变式题
    基于已有题目生成难度相近或指定难度的新题
    """
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
    查询生成题目历史
    """
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
