# -*- coding: utf-8 -*-
"""
内容 API 模块

提供知识库内容的公开查询接口，包括年龄分级、学科、知识点、题目等。
所有接口均无需认证，支持多条件筛选与分页。

主要功能：
    - 年龄分级与学科列表查询
    - 知识点分页查询（支持学科、年龄、难度、关键词筛选）
    - 知识点详情查询
    - 某知识点下的题目列表查询（支持难度与题型筛选）
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
    """
    获取所有年龄分级列表

    Args:
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 年龄分级列表（含编码、名称、最小/最大年龄）
    """
    # 查询所有年龄分级并按最小年龄排序
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
    """
    获取所有学科列表

    Args:
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 学科列表（含编码、名称、图标等）
    """
    # 查询所有学科并按排序号排列
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
    """
    知识点列表接口（分页 + 多条件筛选）

    公开接口，支持按学科、年龄分级、难度、内容类型、关键词筛选。

    Args:
        subject_code (Optional[str]): 学科编码筛选
        age_group_code (Optional[str]): 年龄分级编码筛选
        difficulty_level (Optional[str]): 难度等级筛选
        content_type (Optional[str]): 内容类型筛选
        keyword (Optional[str]): 标题或描述关键词搜索
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页知识点列表（KnowledgeNodeBrief 概要信息）
    """
    # 查询知识点分页结果
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
    """
    知识点详情接口

    根据知识点 UUID 查询详情信息。

    Args:
        node_id (uuid.UUID): 知识点 UUID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 知识点详情（KnowledgeNodeResponse）
    """
    # 查询知识点详情
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
    """
    某知识点下的题目列表接口

    查询指定知识点关联的所有题目，支持按难度等级和题型进一步筛选。

    Args:
        node_id (uuid.UUID): 知识点 UUID
        difficulty_level (Optional[str]): 难度等级筛选
        question_type (Optional[str]): 题型筛选
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 题目列表（QuestionResponse）
    """
    # 查询知识点关联的题目
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
