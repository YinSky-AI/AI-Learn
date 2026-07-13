# -*- coding: utf-8 -*-
"""
AI 出题服务
处理题目生成请求、批次管理、质量检查等
"""

import uuid
import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_generated import (
    GeneratedQuestionBatch,
    GeneratedQuestion,
    QuestionQualityCheck,
    HarnessRun,
)
from app.models.content import KnowledgeNode
from app.schemas.question import (
    QuestionGenerateRequest,
    GeneratedQuestionResponse,
    GenerateResultResponse,
)


async def create_generation_batch(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: QuestionGenerateRequest,
) -> GeneratedQuestionBatch:
    """
    创建题目生成批次
    """
    batch = GeneratedQuestionBatch(
        id=uuid.uuid4(),
        user_id=user_id,
        age_group_code=request.age_group_code,
        subject_code=request.subject_code,
        course_topic=request.course_topic,
        difficulty_level=request.difficulty_level,
        question_types=request.question_types,
        question_count=request.question_count,
        learning_goal=request.learning_goal,
        status="pending",
        prompt_version="v0.1",
    )
    db.add(batch)
    await db.flush()
    return batch


async def save_generated_questions(
    db: AsyncSession,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
    questions: list,
    subject_code: str,
    course_topic: str,
    difficulty_level: str,
) -> List[GeneratedQuestion]:
    """
    保存生成的题目到知识库
    questions: [{question_body, question_type, options, correct_answer, explanation, knowledge_tags, source_prompt}]
    """
    saved_questions = []
    for q in questions:
        # 生成去重指纹
        hash_input = f"{user_id}:{course_topic}:{q['question_body']}"
        similarity_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        gq = GeneratedQuestion(
            id=uuid.uuid4(),
            batch_id=batch_id,
            user_id=user_id,
            knowledge_node_id=q.get("knowledge_node_id"),
            subject_code=subject_code,
            course_topic=course_topic,
            difficulty_level=difficulty_level,
            question_type=q["question_type"],
            question_body=q["question_body"],
            options=q.get("options"),
            correct_answer=q["correct_answer"],
            explanation=q["explanation"],
            knowledge_tags=q.get("knowledge_tags", []),
            source_prompt=q.get("source_prompt", ""),
            similarity_hash=similarity_hash,
            quality_status="unchecked",
        )
        db.add(gq)
        saved_questions.append(gq)

    await db.flush()
    return saved_questions


async def update_batch_status(
    db: AsyncSession,
    batch_id: uuid.UUID,
    status: str,
) -> GeneratedQuestionBatch:
    """
    更新批次状态
    """
    stmt = select(GeneratedQuestionBatch).where(GeneratedQuestionBatch.id == batch_id)
    result = await db.execute(stmt)
    batch = result.scalar_one_or_none()
    if batch is None:
        raise ValueError("批次不存在")
    batch.status = status
    db.add(batch)
    await db.flush()
    return batch


async def get_batch_by_id(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> Optional[GeneratedQuestionBatch]:
    """根据 ID 获取批次"""
    stmt = select(GeneratedQuestionBatch).where(GeneratedQuestionBatch.id == batch_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_user_batches(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_code: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    分页查询用户的生成批次列表
    """
    stmt = select(GeneratedQuestionBatch).where(
        GeneratedQuestionBatch.user_id == user_id
    )
    count_stmt = select(func.count()).select_from(GeneratedQuestionBatch).where(
        GeneratedQuestionBatch.user_id == user_id
    )

    if subject_code:
        stmt = stmt.where(GeneratedQuestionBatch.subject_code == subject_code)
        count_stmt = count_stmt.where(GeneratedQuestionBatch.subject_code == subject_code)
    if status:
        stmt = stmt.where(GeneratedQuestionBatch.status == status)
        count_stmt = count_stmt.where(GeneratedQuestionBatch.status == status)

    total = (await db.execute(count_stmt)).scalar()

    stmt = stmt.order_by(GeneratedQuestionBatch.created_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    batches = list(result.scalars().all())

    return {
        "items": batches,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_batch_questions(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> List[GeneratedQuestion]:
    """获取批次下的所有生成题目"""
    stmt = (
        select(GeneratedQuestion)
        .where(GeneratedQuestion.batch_id == batch_id)
        .order_by(GeneratedQuestion.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def generate_variant(
    db: AsyncSession,
    original_question_id: uuid.UUID,
    user_id: uuid.UUID,
    difficulty_level: Optional[str] = None,
) -> GeneratedQuestion:
    """
    生成变式题（基于已有题目）
    这里仅创建记录，实际 AI 生成逻辑在外部处理
    """
    stmt = select(GeneratedQuestion).where(GeneratedQuestion.id == original_question_id)
    result = await db.execute(stmt)
    original = result.scalar_one_or_none()

    if original is None:
        raise ValueError("原题目不存在")

    # 创建变式题记录（占位，等待 AI 填充内容）
    variant = GeneratedQuestion(
        id=uuid.uuid4(),
        batch_id=original.batch_id,
        user_id=user_id,
        subject_code=original.subject_code,
        course_topic=original.course_topic,
        difficulty_level=difficulty_level or original.difficulty_level,
        question_type=original.question_type,
        question_body="",  # 待 AI 填充
        correct_answer="",  # 待 AI 填充
        explanation="",  # 待 AI 填充
        knowledge_tags=original.knowledge_tags,
        source_prompt=f"variant_of_{original_question_id}",
        parent_question_id=original_question_id,
    )
    db.add(variant)
    await db.flush()
    return variant


async def list_generated_questions(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_code: Optional[str] = None,
    course_topic: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    quality_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    分页查询用户的生成题目历史
    """
    stmt = select(GeneratedQuestion).where(GeneratedQuestion.user_id == user_id)
    count_stmt = select(func.count()).select_from(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id
    )

    if subject_code:
        stmt = stmt.where(GeneratedQuestion.subject_code == subject_code)
        count_stmt = count_stmt.where(GeneratedQuestion.subject_code == subject_code)
    if course_topic:
        stmt = stmt.where(GeneratedQuestion.course_topic.ilike(f"%{course_topic}%"))
        count_stmt = count_stmt.where(GeneratedQuestion.course_topic.ilike(f"%{course_topic}%"))
    if difficulty_level:
        stmt = stmt.where(GeneratedQuestion.difficulty_level == difficulty_level)
        count_stmt = count_stmt.where(GeneratedQuestion.difficulty_level == difficulty_level)
    if quality_status:
        stmt = stmt.where(GeneratedQuestion.quality_status == quality_status)
        count_stmt = count_stmt.where(GeneratedQuestion.quality_status == quality_status)

    total = (await db.execute(count_stmt)).scalar()

    stmt = stmt.order_by(GeneratedQuestion.created_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    questions = list(result.scalars().all())

    return {
        "items": questions,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
