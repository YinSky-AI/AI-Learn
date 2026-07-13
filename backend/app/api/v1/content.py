# -*- coding: utf-8 -*-
"""
内容 API
处理知识点、学科、年龄分级、题目的查询和筛选
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse, paged_response, success_response
from app.schemas.content import (
    AgeGroupResponse,
    SubjectResponse,
    KnowledgeNodeResponse,
    KnowledgeNodeBrief,
    QuestionResponse,
)
from app.services import content_service

router = APIRouter()


# ============ 年龄分级 ============

@router.get("/age-groups", response_model=ApiResponse)
async def list_age_groups(
    db: AsyncSession = Depends(get_db),
):
    """获取所有年龄分级"""
    items = await content_service.get_all_age_groups(db)
    return success_response(
        data=[AgeGroupResponse.model_validate(item) for item in items],
        message="获取年龄分级成功",
    )


# ============ 学科 ============

@router.get("/subjects", response_model=ApiResponse)
async def list_subjects(
    db: AsyncSession = Depends(get_db),
):
    """获取所有学科"""
    items = await content_service.get_all_subjects(db)
    return success_response(
        data=[SubjectResponse.model_validate(item) for item in items],
        message="获取学科列表成功",
    )


# ============ 知识点 ============

@router.get("/knowledge-nodes", response_model=ApiResponse)
async def list_knowledge_nodes(
    subject_code: Optional[str] = Query(None, description="学科编码"),
    age_group_code: Optional[str] = Query(None, description="年龄分级编码"),
    difficulty_level: Optional[str] = Query(None, description="难度等级"),
    content_type: Optional[str] = Query(None, description="内容类型"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """分页查询知识点列表"""
    result = await content_service.list_knowledge_nodes(
        db,
        subject_code=subject_code,
        age_group_code=age_group_code,
        difficulty_level=difficulty_level,
        content_type=content_type,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    items = [KnowledgeNodeBrief.model_validate(item) for item in result["items"]]
    return paged_response(
        data=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/knowledge-nodes/{node_id}", response_model=ApiResponse)
async def get_knowledge_node(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取知识点详情"""
    node = await content_service.get_knowledge_node_by_id(db, node_id)
    if node is None:
        return ApiResponse(code="BIZ_001", message="知识点不存在", data=None)
    return success_response(
        data=KnowledgeNodeResponse.model_validate(node),
        message="获取知识点详情成功",
    )


# ============ 题目 ============

@router.get("/knowledge-nodes/{node_id}/questions", response_model=ApiResponse)
async def list_questions(
    node_id: uuid.UUID,
    difficulty_level: Optional[str] = Query(None, description="难度等级"),
    question_type: Optional[str] = Query(None, description="题型"),
    db: AsyncSession = Depends(get_db),
):
    """获取某知识点下的题目列表"""
    questions = await content_service.list_questions_by_node(
        db,
        knowledge_node_id=node_id,
        difficulty_level=difficulty_level,
        question_type=question_type,
    )
    return success_response(
        data=[QuestionResponse.model_validate(q) for q in questions],
        message="获取题目列表成功",
    )
