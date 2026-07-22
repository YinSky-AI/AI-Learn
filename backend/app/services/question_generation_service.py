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
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_generated import (
    GeneratedQuestionBatch,
    GeneratedQuestion,
    GenerationJob,
)
from app.ai.tools.question_save_tool import QuestionSaveTool
from app.schemas.question import QuestionGenerateRequest


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


async def enqueue_variant_job(
    db: AsyncSession,
    original_question_id: uuid.UUID,
    user_id: uuid.UUID,
    difficulty_level: Optional[str] = None,
) -> GenerationJob:
    """Persist an idempotent variant job without inserting a placeholder question."""
    original = (await db.execute(select(GeneratedQuestion).where(
        GeneratedQuestion.id == original_question_id,
        GeneratedQuestion.user_id == user_id,
    ))).scalar_one_or_none()
    if original is None:
        raise ValueError("原题目不存在")
    target_difficulty = difficulty_level or original.difficulty_level
    key = hashlib.sha256(f"variant:{user_id}:{original_question_id}:{target_difficulty}".encode()).hexdigest()
    existing = (await db.execute(select(GenerationJob).where(GenerationJob.idempotency_key == key))).scalar_one_or_none()
    if existing is not None:
        return existing
    job = GenerationJob(
        user_id=user_id,
        source_question_id=original_question_id,
        target_difficulty=target_difficulty,
        idempotency_key=key,
        status="queued",
    )
    db.add(job)
    await db.flush()
    return job


async def claim_next_generation_job(db: AsyncSession, worker_id: str, lease_seconds: int = 120) -> GenerationJob | None:
    now = datetime.now(timezone.utc)
    job = (await db.execute(
        select(GenerationJob)
        .where(
            GenerationJob.attempts < GenerationJob.max_attempts,
            or_(GenerationJob.status == "queued", (GenerationJob.status == "running") & (GenerationJob.lease_expires_at < now)),
        )
        .order_by(GenerationJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )).scalar_one_or_none()
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.failure_reason = None
    await db.flush()
    return job


async def complete_generation_job(db: AsyncSession, job: GenerationJob, result_question_id: uuid.UUID) -> None:
    if job.status != "running":
        return
    job.status = "succeeded"
    job.result_question_id = result_question_id
    job.lease_owner = None
    job.lease_expires_at = None
    await db.flush()


async def retry_or_fail_generation_job(db: AsyncSession, job: GenerationJob, reason: str) -> None:
    if job.status != "running":
        return
    job.status = "failed" if job.attempts >= job.max_attempts else "queued"
    job.failure_reason = reason[:200]
    job.lease_owner = None
    job.lease_expires_at = None
    await db.flush()


async def process_claimed_generation_job(db: AsyncSession, job: GenerationJob, pipeline) -> None:
    """Run exactly the existing generator + reviewer pipeline for one claimed job."""
    source = (await db.execute(select(GeneratedQuestion).where(GeneratedQuestion.id == job.source_question_id))).scalar_one_or_none()
    if source is None:
        await retry_or_fail_generation_job(db, job, "source_question_missing")
        return
    batch = (await db.execute(select(GeneratedQuestionBatch).where(GeneratedQuestionBatch.id == source.batch_id))).scalar_one_or_none()
    if batch is None:
        await retry_or_fail_generation_job(db, job, "source_batch_missing")
        return
    request = QuestionGenerateRequest(
        age_group_code=batch.age_group_code,
        subject_code=source.subject_code,
        course_topic=source.course_topic,
        difficulty_level=job.target_difficulty,
        question_types=[source.question_type],
        question_count=1,
        learning_goal=None,
    )
    try:
        result = await pipeline.generate(request, str(job.user_id), db)
        saved = await save_generated_questions(
            db, batch.id, job.user_id, result.questions, source.subject_code,
            source.course_topic, job.target_difficulty,
        )
        for question in saved:
            question.parent_question_id = source.id
            question.quality_status = "passed"
        await complete_generation_job(db, job, saved[0].id)
    except Exception:
        await retry_or_fail_generation_job(db, job, "generation_or_review_failed")


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
    user_id: uuid.UUID,
) -> Optional[GeneratedQuestionBatch]:
    """
    根据 ID 获取生成批次

    Args:
        db (AsyncSession): 异步数据库会话
        batch_id (uuid.UUID): 生成批次 UUID

    Returns:
        Optional[GeneratedQuestionBatch]: 当前用户的生成批次，不存在返回 None
    """
    stmt = select(GeneratedQuestionBatch).where(
        GeneratedQuestionBatch.id == batch_id,
        GeneratedQuestionBatch.user_id == user_id,
    )
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
    user_id: uuid.UUID,
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
        .where(
            GeneratedQuestion.batch_id == batch_id,
            GeneratedQuestion.user_id == user_id,
        )
        .order_by(GeneratedQuestion.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def generate_variant(
    db: AsyncSession,
    original_question_id: uuid.UUID,
    user_id: uuid.UUID,
    difficulty_level: Optional[str] = None,
) -> GenerationJob:
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
    return await enqueue_variant_job(db, original_question_id, user_id, difficulty_level)

    variant_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"ai-learn:variant:{user_id}:{original_question_id}:{difficulty_level or 'default'}",
    )
    existing_variant = (await db.execute(
        select(GeneratedQuestion).where(GeneratedQuestion.id == variant_id)
    )).scalar_one_or_none()
    if existing_variant is not None:
        return existing_variant

    stmt = select(GeneratedQuestion).where(
        GeneratedQuestion.id == original_question_id,
        GeneratedQuestion.user_id == user_id,
    )
    result = await db.execute(stmt)
    original = result.scalar_one_or_none()

    if original is None:
        raise ValueError("原题目不存在")

    # 创建终态失败记录，避免向调用方暴露空内容的 pending 题目。
    variant = GeneratedQuestion(
        id=variant_id,
        batch_id=original.batch_id,
        user_id=user_id,
        subject_code=original.subject_code,
        course_topic=original.course_topic,
        difficulty_level=difficulty_level or original.difficulty_level,
        question_type=original.question_type,
        question_body="变式题生成作业已创建，等待可用的生成 Worker。",
        correct_answer="UNAVAILABLE",
        explanation="当前生成服务不可用，作业已记录为失败，可安全重试。",
        knowledge_tags=original.knowledge_tags,
        source_prompt="variant_job_created",
        parent_question_id=original_question_id,
        quality_status="failed",
        generation_status="failed",
        generation_attempts=1,
        generation_failure_reason="worker_unavailable",
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
