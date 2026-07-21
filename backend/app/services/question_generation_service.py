# -*- coding: utf-8 -*-
"""
AI 出题服务模块

提供 AI 题目生成任务的管理业务逻辑，包括同步生成持久化、批次查询、变式题生成等。
新生成接口使用独立的两层 QuestionPipeline；兼容保留原有批次管理方法。

主要功能：
    - 创建生成批次（状态为 pending）
    - 查询生成批次列表与详情
    - 基于已有题目生成变式题
    - 查询生成的题目历史
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
from app.ai.tools.question_save_tool import QuestionSaveTool
from app.schemas.question import (
    QuestionGenerateRequest,
    GeneratedQuestionResponse,
    GenerateResultResponse,
)


async def generate_reviewed_batch(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: QuestionGenerateRequest,
    pipeline,
) -> GeneratedQuestionBatch:
    """在单一事务中生成、审核并保存一个完成批次。"""
    save_tool = QuestionSaveTool(request)
    async with db.begin():
        result = await pipeline.generate(request, user_id, db)
        batch = await save_tool.save_batch(db, result, user_id)
    return batch


async def create_generation_batch(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: QuestionGenerateRequest,
) -> GeneratedQuestionBatch:
    """
    创建题目生成批次

    创建一条状态为 pending 的生成批次记录，实际题目内容待 AI Harness 异步填充。

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        request (QuestionGenerateRequest): 生成请求数据

    Returns:
        GeneratedQuestionBatch: 新创建的生成批次记录
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

    批量保存 AI 生成的题目，自动计算去重指纹（similarity_hash）。

    Args:
        db (AsyncSession): 异步数据库会话
        batch_id (uuid.UUID): 生成批次 UUID
        user_id (uuid.UUID): 用户 UUID
        questions (list): 题目数据列表，每项包含 question_body、question_type、options 等字段
        subject_code (str): 学科编码
        course_topic (str): 课程主题
        difficulty_level (str): 难度等级

    Returns:
        List[GeneratedQuestion]: 保存后的生成题目记录列表
    """
    saved_questions = []
    for q in questions:
        # 生成去重指纹：基于用户 ID + 课程主题 + 题目内容
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

    Args:
        db (AsyncSession): 异步数据库会话
        batch_id (uuid.UUID): 生成批次 UUID
        status (str): 新状态（pending / running / completed / failed）

    Returns:
        GeneratedQuestionBatch: 更新后的批次记录

    Raises:
        ValueError: 批次不存在时抛出
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
) -> Optional[GeneratedQuestion]:
    """
    根据 ID 获取生成批次

    Args:
        db (AsyncSession): 异步数据库会话
        batch_id (uuid.UUID): 生成批次 UUID

    Returns:
        Optional[GeneratedQuestion]: 生成记录，不存在返回 None
    """
    stmt = select(GeneratedQuestion).where(GeneratedQuestion.id == batch_id)
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

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        subject_code (Optional[str]): 学科编码筛选
        status (Optional[str]): 批次状态筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        dict: 分页生成批次列表
    """
    stmt = select(GeneratedQuestionBatch).where(
        GeneratedQuestionBatch.user_id == user_id
    )
    count_stmt = select(func.count()).select_from(GeneratedQuestionBatch).where(
        GeneratedQuestionBatch.user_id == user_id
    )

    # 条件筛选
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
    """获取批次下的所有生成题目

    Args:
        db (AsyncSession): 异步数据库会话
        batch_id (uuid.UUID): 生成批次 UUID

    Returns:
        List[GeneratedQuestion]: 该批次下的生成题目列表
    """
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

    创建变式题占位记录，复制原题的元数据（学科、主题、题型等），
    实际题目内容（题干、答案、解析）由外部 AI Harness 异步填充。

    Args:
        db (AsyncSession): 异步数据库会话
        original_question_id (uuid.UUID): 原题 UUID
        user_id (uuid.UUID): 用户 UUID
        difficulty_level (Optional[str]): 目标难度，默认与原题相同

    Returns:
        GeneratedQuestion: 创建的变式题占位记录

    Raises:
        ValueError: 原题目不存在时抛出
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

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        subject_code (Optional[str]): 学科编码筛选
        course_topic (Optional[str]): 课程主题关键词筛选
        difficulty_level (Optional[str]): 难度等级筛选
        quality_status (Optional[str]): 质量状态筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        dict: 分页生成题目历史列表
    """
    stmt = select(GeneratedQuestion).where(GeneratedQuestion.user_id == user_id)
    count_stmt = select(func.count()).select_from(GeneratedQuestion).where(
        GeneratedQuestion.user_id == user_id
    )

    # 条件筛选
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
