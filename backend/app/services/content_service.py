# -*- coding: utf-8 -*-
"""
内容服务
处理知识库内容的查询、筛选
"""

import uuid
from typing import List, Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import AgeGroup, Subject, KnowledgeNode, Question


# ============ 年龄分级 ============

async def get_all_age_groups(db: AsyncSession) -> List[AgeGroup]:
    """获取所有年龄分级"""
    stmt = select(AgeGroup).order_by(AgeGroup.min_age)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_age_group_by_code(db: AsyncSession, code: str) -> Optional[AgeGroup]:
    """根据编码获取年龄分级"""
    stmt = select(AgeGroup).where(AgeGroup.code == code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ============ 学科 ============

async def get_all_subjects(db: AsyncSession) -> List[Subject]:
    """获取所有学科"""
    stmt = select(Subject).order_by(Subject.sort_order)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_subject_by_code(db: AsyncSession, code: str) -> Optional[Subject]:
    """根据编码获取学科"""
    stmt = select(Subject).where(Subject.code == code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ============ 知识点 ============

async def get_knowledge_node_by_id(
    db: AsyncSession,
    node_id: uuid.UUID,
) -> Optional[KnowledgeNode]:
    """根据 ID 获取知识点"""
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
    """
    stmt = select(KnowledgeNode).where(KnowledgeNode.is_active == True)
    count_stmt = select(func.count()).select_from(KnowledgeNode).where(
        KnowledgeNode.is_active == True
    )

    # 条件筛选
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
    if keyword:
        search_filter = or_(
            KnowledgeNode.title.ilike(f"%{keyword}%"),
            KnowledgeNode.description.ilike(f"%{keyword}%"),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    # 排序
    stmt = stmt.order_by(KnowledgeNode.sort_order, KnowledgeNode.created_at)

    # 总数
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
    """根据 ID 获取题目"""
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
    """
    stmt = select(Question).where(Question.knowledge_node_id == knowledge_node_id)

    if difficulty_level:
        stmt = stmt.where(Question.difficulty_level == difficulty_level)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)

    stmt = stmt.order_by(Question.sort_order)
    result = await db.execute(stmt)
    return list(result.scalars().all())
