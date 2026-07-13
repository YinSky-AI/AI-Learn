# -*- coding: utf-8 -*-
"""
学习服务
处理学习会话创建、答题、会话完成等业务逻辑
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Question
from app.models.learning import LearningSession, Answer


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    knowledge_node_id: uuid.UUID,
    difficulty_level: str,
) -> LearningSession:
    """
    创建学习会话
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
) -> LearningSession:
    """
    根据 ID 获取学习会话
    """
    stmt = select(LearningSession).where(LearningSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BIZ_001", "message": "学习会话不存在"},
        )
    return session


async def submit_answer(
    db: AsyncSession,
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    user_answer: str,
    time_spent_seconds: int,
) -> Answer:
    """
    提交答案
    1. 获取题目，判断正误
    2. 创建答题记录
    3. 更新会话统计
    """
    # 获取会话
    session = await get_session_by_id(db, session_id)

    # 检查会话状态
    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BIZ_001", "message": "该学习会话已结束"},
        )

    # 获取题目
    stmt = select(Question).where(Question.id == question_id)
    result = await db.execute(stmt)
    question = result.scalar_one_or_none()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BIZ_001", "message": "题目不存在"},
        )

    # 判断正误
    is_correct = user_answer.strip().upper() == question.correct_answer.strip().upper()

    # 创建答题记录
    answer = Answer(
        id=uuid.uuid4(),
        session_id=session_id,
        question_id=question_id,
        user_answer=user_answer,
        is_correct=is_correct,
        time_spent_seconds=time_spent_seconds,
        answered_at=datetime.now(timezone.utc),
    )
    db.add(answer)

    # 更新会话统计
    session.total_questions += 1
    if is_correct:
        session.correct_count += 1

    await db.flush()

    return answer


async def complete_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> LearningSession:
    """
    完成学习会话
    """
    session = await get_session_by_id(db, session_id)

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
) -> dict:
    """
    获取学习会话统计信息
    """
    session = await get_session_by_id(db, session_id)

    # 计算总用时
    if session.completed_at and session.started_at:
        total_time = int(
            (session.completed_at - session.started_at).total_seconds()
        )
    else:
        total_time = int(
            (datetime.now(timezone.utc) - session.started_at).total_seconds()
        )

    # 计算正确率
    accuracy = (
        (session.correct_count / session.total_questions * 100)
        if session.total_questions > 0
        else 0.0
    )

    return {
        "session_id": session.id,
        "status": session.status,
        "correct_count": session.correct_count,
        "total_questions": session.total_questions,
        "accuracy_rate": round(accuracy, 1),
        "total_time_seconds": total_time,
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
