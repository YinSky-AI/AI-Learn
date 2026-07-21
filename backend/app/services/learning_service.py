# -*- coding: utf-8 -*-
"""
学习会话服务模块

提供学习会话的生命周期管理业务逻辑，包括会话创建、答题提交、会话完成与统计查询。
所有操作均绑定到具体用户，答题后自动判题并更新会话统计。

主要功能：
    - 创建学习会话（绑定知识点与难度）
    - 提交答案（自动判题、更新统计）
    - 完成会话（状态标记与统计结算）
    - 会话统计与历史列表查询
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.content import Question
from app.models.learning import LearningSession, Answer
from app.models.user import User
from app.services.wrong_book_service import WrongBookService
from app.services.behavior_service import BehaviorService

def _build_answer_result(answer: Answer, question: Question) -> dict:
    knowledge_point = question.knowledge_node_rel.title if question.knowledge_node_rel is not None else None
    tutor_prompt = None
    if not answer.is_correct:
        topic = knowledge_point or "这道题的核心知识点"
        tutor_prompt = (
            f"我在“{topic}”这道题上回答错了。"
            f"我原来的思路是“{answer.user_answer.strip()}”。"
            "请不要直接告诉我完整答案，先用一个问题引导我找出题目条件与运算含义的关系。"
        )
    return {
        "id": answer.id,
        "is_correct": answer.is_correct,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "knowledge_point": knowledge_point,
        "tutor_prompt": tutor_prompt,
        "time_spent_seconds": answer.time_spent_seconds,
    }



async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    knowledge_node_id: uuid.UUID,
    difficulty_level: str,
) -> LearningSession:
    """
    创建学习会话

    Args:
        db (AsyncSession): 异步数据库会话
        user_id (uuid.UUID): 用户 UUID
        knowledge_node_id (uuid.UUID): 知识点 UUID
        difficulty_level (str): 难度等级

    Returns:
        LearningSession: 新创建的学习会话 ORM 对象
    """
    session = LearningSession(
        id=uuid.uuid4(),
        user_id=user_id,
        knowledge_node_id=knowledge_node_id,
        difficulty_level=difficulty_level,
        status="in_progress",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()
    return session


async def get_session_by_id(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> LearningSession:
    """
    根据 ID 获取学习会话

    Args:
        db (AsyncSession): 异步数据库会话
        session_id (uuid.UUID): 学习会话 UUID
        user_id (uuid.UUID): 当前认证用户 UUID

    Returns:
        LearningSession: 学习会话 ORM 对象

    Raises:
        HTTPException: 会话不存在时抛出 404
    """
    stmt = select(LearningSession).where(LearningSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BIZ_001", "message": "学习会话不存在"},
        )
    if session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AUTH_004", "message": "无权访问该学习会话"},
        )
    return session


async def submit_answer(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    question_id: uuid.UUID,
    answer_id: uuid.UUID,
    user_answer: str,
    time_spent_seconds: int,
) -> dict:
    """
    提交答案

    完整的答题处理流程：
        1. 获取并校验会话状态（必须为 in_progress）
        2. 查询题目并判断正误（不区分大小写的字符串比较）
        3. 创建答题记录
        4. 更新会话统计（总题数、正确数）

    Args:
        db (AsyncSession): 异步数据库会话
        session_id (uuid.UUID): 学习会话 UUID
        user_id (uuid.UUID): 当前认证用户 UUID
        question_id (uuid.UUID): 题目 UUID
        user_answer (str): 用户提交的答案
        time_spent_seconds (int): 答题用时（秒）

    Returns:
        dict: 答题记录及题目反馈

    Raises:
        HTTPException: 会话不存在、已结束或题目不存在时抛出
    """
    # 获取会话并校验状态
    session = await get_session_by_id(db, session_id, user_id=user_id)

    # 获取题目信息
    existing_result = await db.execute(select(Answer).where(Answer.id == answer_id))
    existing_answer = existing_result.scalar_one_or_none()

    stmt = (
        select(Question)
        .options(joinedload(Question.knowledge_node_rel))
        .where(Question.id == (existing_answer.question_id if existing_answer else question_id))
    )
    if existing_answer is not None:
        if (
            existing_answer.session_id != session_id
            or existing_answer.question_id != question_id
            or existing_answer.user_answer != user_answer
            or existing_answer.time_spent_seconds != time_spent_seconds
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "BIZ_001", "message": "作答事件与原请求不一致"},
            )
        result = await db.execute(stmt)
        question = result.scalar_one_or_none()
        if question is None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"code": "BIZ_001", "message": "原题已删除，无法回放该作答结果"},
            )
        return _build_answer_result(existing_answer, question)

    result = await db.execute(stmt)
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BIZ_001", "message": "题目不存在"},
        )

    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BIZ_001", "message": "该学习会话已结束"},
        )

    # 判断正误（去除空白并不区分大小写比较）
    is_correct = user_answer.strip().upper() == question.correct_answer.strip().upper()

    # 创建答题记录
    answer = Answer(
        id=answer_id,
        session_id=session_id,
        question_id=question_id,
        user_answer=user_answer,
        is_correct=is_correct,
        time_spent_seconds=time_spent_seconds,
        answered_at=datetime.now(timezone.utc),
    )
    db.add(answer)
    await db.flush()

    # 答题记录和错题收录使用同一个数据库事务，任一失败都会统一回滚。
    if not is_correct:
        subject = question.knowledge_node_rel.subject_code if question.knowledge_node_rel else "未分类"
        await WrongBookService(db).record_wrong_answer(
            user_id=user_id,
            question_id=question_id,
            answer_id=answer.id,
            subject=subject,
            wrong_answer=user_answer,
        )

    # 更新会话统计
    session.total_questions += 1
    if is_correct:
        session.correct_count += 1

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user:
        await BehaviorService(db).update_after_answer(
            user_id=user_id,
            answer_id=answer.id,
            question=question,
            is_correct=is_correct,
            response_time_ms=time_spent_seconds * 1000,
            answered_at=answer.answered_at,
        )
    await db.flush()

    return _build_answer_result(answer, question)


async def complete_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> LearningSession:
    """
    完成学习会话

    将指定会话状态从 in_progress 标记为 completed，并记录完成时间。

    Args:
        db (AsyncSession): 异步数据库会话
        session_id (uuid.UUID): 学习会话 UUID

    Returns:
        LearningSession: 更新后的学习会话对象

    Raises:
        HTTPException: 会话不存在或已结束时抛出
    """
    session = await get_session_by_id(db, session_id, user_id=user_id)

    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BIZ_001", "message": "该会话已结束，无法重复完成"},
        )

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.add(session)
    await db.flush()

    return session


async def get_session_stats(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    """
    获取学习会话统计信息

    聚合指定会话的答题数据，包括总题数、正确数、正确率、答题总用时、会话持续时间等。

    Args:
        db (AsyncSession): 异步数据库会话
        session_id (uuid.UUID): 学习会话 UUID

    Returns:
        dict: 会话统计字典
    """
    session = await get_session_by_id(db, session_id, user_id=user_id)

    total = session.total_questions or 0
    correct = session.correct_count or 0
    accuracy = int(correct * 100 / total) if total > 0 else 0

    # 计算答题总用时（从 Answer 表聚合）
    stmt = select(func.sum(Answer.time_spent_seconds)).where(
        Answer.session_id == session_id
    )
    result = await db.execute(stmt)
    total_time = result.scalar_one_or_none() or 0

    # 计算会话持续时间（已结束取完成时间，未结束取当前时间）
    started_at = session.started_at or datetime.now(timezone.utc)
    ended_at = session.completed_at or datetime.now(timezone.utc)
    session_duration = int((ended_at - started_at).total_seconds())

    return {
        "session_id": str(session_id),
        "total_questions": total,
        "correct_count": correct,
        "accuracy": accuracy,
        "total_time": total_time,
        "session_duration": session_duration,
        "status": session.status,
    }


async def list_user_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    获取用户的学习会话列表
    """
    stmt = (
        select(LearningSession)
        .where(LearningSession.user_id == user_id)
        .order_by(LearningSession.started_at.desc())
    )
    count_stmt = (
        select(func.count())
        .select_from(LearningSession)
        .where(LearningSession.user_id == user_id)
    )

    total = (await db.execute(count_stmt)).scalar()
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    sessions = list(result.scalars().all())

    return {
        "items": sessions,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_session_answers(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list:
    """
    获取某个会话的所有答题记录
    """
    stmt = (
        select(Answer)
        .where(Answer.session_id == session_id)
        .order_by(Answer.answered_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
