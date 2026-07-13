# -*- coding: utf-8 -*-
"""
进度服务
处理学习进度统计、趋势分析等
"""

import uuid
from typing import Optional

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import LearningSession, Answer
from app.models.content import KnowledgeNode


async def get_user_learning_progress(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """
    获取用户总体学习进度
    """
    # 总会话数
    total_sessions_stmt = select(func.count()).where(
        LearningSession.user_id == user_id
    )
    total_sessions = (await db.execute(total_sessions_stmt)).scalar() or 0

    # 已完成会话数
    completed_sessions_stmt = select(func.count()).where(
        LearningSession.user_id == user_id,
        LearningSession.status == "completed",
    )
    completed_sessions = (await db.execute(completed_sessions_stmt)).scalar() or 0

    # 总答题数
    total_answers_stmt = (
        select(func.count())
        .select_from(Answer)
        .join(LearningSession, Answer.session_id == LearningSession.id)
        .where(LearningSession.user_id == user_id)
    )
    total_answers = (await db.execute(total_answers_stmt)).scalar() or 0

    # 总正确数
    correct_answers_stmt = (
        select(func.count())
        .select_from(Answer)
        .join(LearningSession, Answer.session_id == LearningSession.id)
        .where(LearningSession.user_id == user_id, Answer.is_correct == True)
    )
    correct_answers = (await db.execute(correct_answers_stmt)).scalar() or 0

    # 正确率
    accuracy = (correct_answers / total_answers * 100) if total_answers > 0 else 0.0

    # 总用时
    total_time_stmt = (
        select(func.sum(Answer.time_spent_seconds))
        .select_from(Answer)
        .join(LearningSession, Answer.session_id == LearningSession.id)
        .where(LearningSession.user_id == user_id)
    )
    total_time = (await db.execute(total_time_stmt)).scalar() or 0

    return {
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "total_answers": total_answers,
        "correct_answers": correct_answers,
        "accuracy_rate": round(accuracy, 1),
        "total_time_seconds": total_time,
    }


async def get_subject_progress(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_code: str,
) -> dict:
    """
    获取某学科的学习进度
    """
    # 该学科下已学习的知识点数
    nodes_stmt = (
        select(func.count(func.distinct(LearningSession.knowledge_node_id)))
        .where(
            LearningSession.user_id == user_id,
        )
        .join(KnowledgeNode, LearningSession.knowledge_node_id == KnowledgeNode.id)
        .where(KnowledgeNode.subject_code == subject_code)
    )
    learned_nodes = (await db.execute(nodes_stmt)).scalar() or 0

    # 该学科总知识点数
    total_nodes_stmt = select(func.count()).where(
        KnowledgeNode.subject_code == subject_code,
        KnowledgeNode.is_active == True,
    )
    total_nodes = (await db.execute(total_nodes_stmt)).scalar() or 0

    # 正确率
    accuracy_stmt = (
        select(
            func.count().filter(Answer.is_correct == True),
            func.count(),
        )
        .select_from(Answer)
        .join(LearningSession, Answer.session_id == LearningSession.id)
        .join(KnowledgeNode, LearningSession.knowledge_node_id == KnowledgeNode.id)
        .where(
            LearningSession.user_id == user_id,
            KnowledgeNode.subject_code == subject_code,
        )
    )
    row = (await db.execute(accuracy_stmt)).one_or_none()
    correct = row[0] if row else 0
    total = row[1] if row else 0
    accuracy = (correct / total * 100) if total > 0 else 0.0

    return {
        "subject_code": subject_code,
        "learned_nodes": learned_nodes,
        "total_nodes": total_nodes,
        "coverage_rate": round(learned_nodes / total_nodes * 100, 1) if total_nodes > 0 else 0.0,
        "accuracy_rate": round(accuracy, 1),
    }


async def get_recent_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 10,
) -> list:
    """
    获取最近的学习会话
    """
    stmt = (
        select(LearningSession)
        .where(LearningSession.user_id == user_id)
        .order_by(LearningSession.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_difficulty_distribution(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """
    获取用户各难度的答题分布
    """
    stmt = (
        select(
            LearningSession.difficulty_level,
            func.count(Answer.id).label("total"),
            func.sum(case((Answer.is_correct == True, 1), else_=0)).label("correct"),
        )
        .select_from(Answer)
        .join(LearningSession, Answer.session_id == LearningSession.id)
        .where(LearningSession.user_id == user_id)
        .group_by(LearningSession.difficulty_level)
    )
    result = await db.execute(stmt)
    rows = result.all()

    distribution = {}
    for row in rows:
        level = row[0]
        total = row[1]
        correct = row[2] or 0
        distribution[level] = {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total * 100, 1) if total > 0 else 0.0,
        }

    return distribution
