# -*- coding: utf-8 -*-
"""
生成题目知识库检索服务
提供去重、相似题检索、错题复习等功能
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
    使用 ILIKE 进行简单模糊匹配，生产环境可升级为向量检索
    """
    # 按用户 + 学科 + 主题筛选
    stmt = select(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id,
        GeneratedQuestion.subject_code == subject_code,
    )

    # 模糊匹配
    if course_topic:
        stmt = stmt.where(
            GeneratedQuestion.course_topic.ilike(f"%{course_topic}%")
        )

    # 题干关键词匹配
    keywords = question_body[:50]  # 取前50字作为关键词
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
    返回 True 表示存在高度相似的题目
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
    """
    stmt = select(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id,
    )
    count_stmt = select(func.count()).select_from(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id,
    )

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
    获取错题列表（通过关联答题记录）
    简单实现：返回所有 quality_status 为 failed 的题目
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
    获取变式题链（通过 parent_question_id 递归查找）
    """
    stmt = select(GeneratedQuestion).where(
        or_(
            GeneratedQuestion.id == question_id,
            GeneratedQuestion.parent_question_id == question_id,
        )
    ).order_by(GeneratedQuestion.created_at)

    result = await db.execute(stmt)
    return list(result.scalars().all())
