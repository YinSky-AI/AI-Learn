# -*- coding: utf-8 -*-
"""
题库记忆服务模块

管理用户对题目的记忆状态与掌握程度，支持基于掌握状态的智能筛选。
记忆状态用于个性化出题，避免重复推送已熟练掌握的题目。

主要功能：
    - 创建/更新题目记忆状态
    - 查询用户某题目的记忆状态
    - 筛选用户未掌握或需要复习的题目
"""

import uuid
from typing import List, Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_generated import GeneratedQuestion


async def search_similar_questions(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_code: str,
    course_topic: str,
    question_body: str,
    limit: int = 5,
) -> List[GeneratedQuestion]:
    """
    搜索相似题目（用于去重检查）

    使用 ILIKE 进行简单模糊匹配，按用户、学科、主题、题干关键词筛选。
    生产环境可升级为向量检索以获得更精准的相似度计算。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        subject_code (str): 学科编码
        course_topic (str): 课程主题
        question_body (str): 题目题干（取前 50 字作为关键词）
        limit (int): 返回数量限制，默认 5

    Returns:
        List[GeneratedQuestion]: 相似题目列表
    """
    # 按用户 + 学科筛选基础范围
    stmt = select(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id,
        GeneratedQuestion.subject_code == subject_code,
    )

    # 按课程主题模糊匹配
    if course_topic:
        stmt = stmt.where(
            GeneratedQuestion.course_topic.ilike(f"%{course_topic}%")
        )

    # 按题干关键词模糊匹配（取前 50 字作为关键词）
    keywords = question_body[:50]
    stmt = stmt.where(
        or_(
            GeneratedQuestion.question_body.ilike(f"%{keywords}%"),
            GeneratedQuestion.course_topic.ilike(f"%{course_topic}%"),
        )
    )

    stmt = stmt.order_by(GeneratedQuestion.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def check_duplicate(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_code: str,
    course_topic: str,
    question_body: str,
    similarity_threshold: float = 0.8,
) -> bool:
    """
    检查是否已存在相似题目（简单实现）

    调用 search_similar_questions 检索相似题目，若存在任意相似题则视为重复。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        subject_code (str): 学科编码
        course_topic (str): 课程主题
        question_body (str): 题目题干
        similarity_threshold (float): 相似度阈值（当前实现未使用，预留参数）

    Returns:
        bool: 存在相似题目返回 True，否则返回 False
    """
    similar = await search_similar_questions(
        db, user_id, subject_code, course_topic, question_body, limit=1
    )
    return len(similar) > 0


async def get_user_question_bank(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_code: Optional[str] = None,
    quality_status: str = "passed",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    获取用户的生成题目知识库

    分页查询用户已生成的题目，默认仅返回质量检查通过的题目。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        subject_code (Optional[str]): 学科编码筛选
        quality_status (str): 质量状态筛选，默认 "passed"
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        dict: 分页生成题目列表
    """
    stmt = select(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id,
    )
    count_stmt = select(func.count()).select_from(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id,
    )

    # 条件筛选
    if quality_status:
        stmt = stmt.where(GeneratedQuestion.quality_status == quality_status)
        count_stmt = count_stmt.where(GeneratedQuestion.quality_status == quality_status)
    if subject_code:
        stmt = stmt.where(GeneratedQuestion.subject_code == subject_code)
        count_stmt = count_stmt.where(GeneratedQuestion.subject_code == subject_code)

    total = (await db.execute(count_stmt)).scalar()

    stmt = stmt.order_by(GeneratedQuestion.created_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_wrong_questions(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_code: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    获取错题列表

    简单实现：返回所有 quality_status 为 failed 的题目作为错题。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        subject_code (Optional[str]): 学科编码筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        dict: 分页错题列表
    """
    stmt = select(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id,
        GeneratedQuestion.quality_status == "failed",
    )
    count_stmt = select(func.count()).select_from(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id,
        GeneratedQuestion.quality_status == "failed",
    )

    if subject_code:
        stmt = stmt.where(GeneratedQuestion.subject_code == subject_code)
        count_stmt = count_stmt.where(GeneratedQuestion.subject_code == subject_code)

    total = (await db.execute(count_stmt)).scalar()

    stmt = stmt.order_by(GeneratedQuestion.created_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_variant_chain(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> List[GeneratedQuestion]:
    """
    获取变式题链

    查询指定题目及其所有直接变式题（通过 parent_question_id 关联）。

    Args:
        db (AsyncSession): 异步数据库会话
        question_id (uuid.UUID): 原题 UUID

    Returns:
        List[GeneratedQuestion]: 包含原题及其变式题的列表，按创建时间排序
    """
    stmt = select(GeneratedQuestion).where(
        or_(
            GeneratedQuestion.id == question_id,
            GeneratedQuestion.parent_question_id == question_id,
        )
    ).order_by(GeneratedQuestion.created_at)

    result = await db.execute(stmt)
    return list(result.scalars().all())
