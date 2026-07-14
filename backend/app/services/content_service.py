# -*- coding: utf-8 -*-
"""
内容服务模块

提供知识库内容的查询与筛选业务逻辑，包括年龄分级、学科、知识点、题目等。
所有接口均为公开查询，无需用户认证。

主要功能：
    - 年龄分级与学科列表查询
    - 知识点分页查询（支持多条件筛选）
    - 知识点详情与关联题目查询
"""

import uuid
from typing import List, Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import AgeGroup, Subject, KnowledgeNode, Question


# ============ 年龄分级 ============

async def get_all_age_groups(db: AsyncSession) -> List[AgeGroup]:
    """
    获取所有年龄分级

    Args:
        db (AsyncSession): 异步数据库会话

    Returns:
        List[AgeGroup]: 按最小年龄排序的年龄分级列表
    """
    stmt = select(AgeGroup).order_by(AgeGroup.min_age)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_age_group_by_code(db: AsyncSession, code: str) -> Optional[AgeGroup]:
    """
    根据编码获取年龄分级

    Args:
        db (AsyncSession): 异步数据库会话
        code (str): 年龄分级编码

    Returns:
        Optional[AgeGroup]: 年龄分级对象，不存在返回 None
    """
    stmt = select(AgeGroup).where(AgeGroup.code == code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ============ 学科 ============

async def get_all_subjects(db: AsyncSession) -> List[Subject]:
    """
    获取所有学科

    Args:
        db (AsyncSession): 异步数据库会话

    Returns:
        List[Subject]: 按排序号排列的学科列表
    """
    stmt = select(Subject).order_by(Subject.sort_order)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_subject_by_code(db: AsyncSession, code: str) -> Optional[Subject]:
    """
    根据编码获取学科

    Args:
        db (AsyncSession): 异步数据库会话
        code (str): 学科编码

    Returns:
        Optional[Subject]: 学科对象，不存在返回 None
    """
    stmt = select(Subject).where(Subject.code == code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ============ 知识点 ============

async def get_knowledge_node_by_id(
    db: AsyncSession,
    node_id: uuid.UUID,
) -> Optional[KnowledgeNode]:
    """
    根据 ID 获取知识点

    Args:
        db (AsyncSession): 异步数据库会话
        node_id (uuid.UUID): 知识点 UUID

    Returns:
        Optional[KnowledgeNode]: 知识点对象，不存在返回 None
    """
    stmt = select(KnowledgeNode).where(KnowledgeNode.id == node_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_knowledge_nodes(
    db: AsyncSession,
    subject_code: Optional[str] = None,
    age_group_code: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    content_type: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    分页查询知识点列表（支持多条件筛选）

    Args:
        db (AsyncSession): 异步数据库会话
        subject_code (Optional[str]): 学科编码筛选
        age_group_code (Optional[str]): 年龄分级编码筛选
        difficulty_level (Optional[str]): 难度等级筛选
        content_type (Optional[str]): 内容类型筛选
        keyword (Optional[str]): 标题或描述关键词搜索
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        dict: 分页知识点列表
    """
    stmt = select(KnowledgeNode).where(KnowledgeNode.is_active == True)
    count_stmt = select(func.count()).select_from(KnowledgeNode).where(
        KnowledgeNode.is_active == True
    )

    # 条件筛选：学科、年龄分级、难度、内容类型
    if subject_code:
        stmt = stmt.where(KnowledgeNode.subject_code == subject_code)
        count_stmt = count_stmt.where(KnowledgeNode.subject_code == subject_code)
    if age_group_code:
        stmt = stmt.where(KnowledgeNode.age_group_code == age_group_code)
        count_stmt = count_stmt.where(KnowledgeNode.age_group_code == age_group_code)
    if difficulty_level:
        stmt = stmt.where(KnowledgeNode.difficulty_level == difficulty_level)
        count_stmt = count_stmt.where(KnowledgeNode.difficulty_level == difficulty_level)
    if content_type:
        stmt = stmt.where(KnowledgeNode.content_type == content_type)
        count_stmt = count_stmt.where(KnowledgeNode.content_type == content_type)
    # 关键词模糊匹配（标题 + 描述）
    if keyword:
        search_filter = or_(
            KnowledgeNode.title.ilike(f"%{keyword}%"),
            KnowledgeNode.description.ilike(f"%{keyword}%"),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    # 排序：先按 sort_order 再按创建时间
    stmt = stmt.order_by(KnowledgeNode.sort_order, KnowledgeNode.created_at)

    # 查询总数
    total = (await db.execute(count_stmt)).scalar()

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    return {
        "items": nodes,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============ 题目 ============

async def get_question_by_id(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> Optional[Question]:
    """
    根据 ID 获取题目

    Args:
        db (AsyncSession): 异步数据库会话
        question_id (uuid.UUID): 题目 UUID

    Returns:
        Optional[Question]: 题目对象，不存在返回 None
    """
    stmt = select(Question).where(Question.id == question_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_questions_by_node(
    db: AsyncSession,
    knowledge_node_id: uuid.UUID,
    difficulty_level: Optional[str] = None,
    question_type: Optional[str] = None,
) -> List[Question]:
    """
    获取某知识点下的题目列表

    Args:
        db (AsyncSession): 异步数据库会话
        knowledge_node_id (uuid.UUID): 知识点 UUID
        difficulty_level (Optional[str]): 难度等级筛选
        question_type (Optional[str]): 题型筛选

    Returns:
        List[Question]: 题目列表
    """
    stmt = select(Question).where(Question.knowledge_node_id == knowledge_node_id)

    # 按难度和题型筛选
    if difficulty_level:
        stmt = stmt.where(Question.difficulty_level == difficulty_level)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)

    stmt = stmt.order_by(Question.sort_order)
    result = await db.execute(stmt)
    return list(result.scalars().all())
