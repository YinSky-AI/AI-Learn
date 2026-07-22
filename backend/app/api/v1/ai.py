# -*- coding: utf-8 -*-
"""
AI 助手与审计进化 API 模块

提供四角色智能辅导、错题分析、技能管理、进化记录查询、错误日志查询等接口。
部分接口支持可选认证，未登录用户也可使用基础 AI 聊天功能。

主要功能：
    - AI 题目解析（占位）
    - 四角色苏格拉底式辅导（支持上下文与多轮对话）
    - 错题分析（占位）
    - 技能列表与详情查询（审计进化）
    - 用户行为档案查询
    - 进化记录与错误日志查询
    - 用户会话记忆查询
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.ai.harness import TutorHarness
from app.ai.tutor import TutorMessage, TutorResponse
from app.core.database import get_db
from app.core.deps import get_current_user_id, get_current_user, get_current_user_id_optional
from app.models.ai_generated import Skill, SessionMemory, ErrorLog, EvolutionRecord, HarnessRun
from app.models.content import Question
from app.models.learning import Answer, LearningSession
from app.models.user import User
from app.schemas.common import ApiResponse, paged_response, success_response
from app.services.course_service import save_chat_message

logger = logging.getLogger(__name__)

router = APIRouter()


# ==============================
# Chat 端点请求/响应模型
# ==============================

class ChatRequest(BaseModel):
    """AI 聊天请求"""
    message: str = Field(..., min_length=1, max_length=8000, description="用户消息")
    message_type: str = Field(default="question", max_length=32, description="消息类型")
    topic: str = Field(default="", max_length=200, description="当前知识点")
    age_group: str = Field(default="9-12", max_length=20, description="学生年龄段")
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="上下文信息，可包含 courseId, lessonId, subject, ageGroup 等",
    )
    conversationHistory: Optional[List[Dict[str, str]]] = Field(
        default=None, max_length=20,
        description="对话历史，格式为 [{role, content}, ...]",
    )


# ==============================
# AI 助手功能
# ==============================

@router.get("/explain/{question_id}")
async def explain_question(
    question_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    AI 解析题目接口（占位）

    返回题目的 AI 详细解析和关联知识点讲解。当前为占位实现，待接入大语言模型。

    Args:
        question_id (uuid.UUID): 题目 UUID
        user_id (uuid.UUID): 当前登录用户 ID

    Returns:
        ApiResponse: 解析结果（占位数据）
    """
    # TODO: 实际调用 AI 模型进行题目解析
    return success_response(
        data={
            "question_id": str(question_id),
            "explanation": "暂未实现：AI 解析功能需要接入大语言模型",
            "related_knowledge": [],
        },
        message="AI 解析请求已记录",
    )


@router.get("/stream/{session_id}")
async def stream_explanation(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    流式 AI 对话接口（SSE 端点占位）

    预留的 SSE 流式对话端点，实际实现需返回 StreamingResponse。

    Args:
        session_id (uuid.UUID): 会话 ID
        user_id (uuid.UUID): 当前登录用户 ID

    Returns:
        ApiResponse: 占位响应
    """
    # TODO: 实现 SSE 流式返回 AI 回复
    return success_response(
        data={
            "session_id": str(session_id),
            "message": "SSE 流式端点待实现",
        },
        message="流式对话端点",
    )


@router.post("/error-analysis")
async def analyze_errors(
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    错题分析接口（占位）

    AI 分析用户最近的错误答题模式，识别薄弱知识点并提供针对性学习建议。
    当前为占位实现，待接入 AI 分析能力。

    Args:
        user_id (uuid.UUID): 当前登录用户 ID

    Returns:
        ApiResponse: 错题分析结果（占位数据）
    """
    # TODO: 实际调用 AI 模型分析用户错题模式
    return success_response(
        data={
            "error_patterns": [],
            "weak_knowledge_nodes": [],
            "recommendations": [],
        },
        message="错题分析请求已记录",
    )


# ==============================
# 四角色辅导聊天
# ==============================


@router.post("/chat", response_model=ApiResponse[TutorResponse])
async def chat(
    body: ChatRequest,
    user_id: Optional[uuid.UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """返回确定性的苏格拉底式辅导消息，不调用外部 AI。"""

    try:
        context = dict(body.context or {})
        context["student_message"] = body.message
        context.setdefault("topic", body.topic)
        context.setdefault("age_group", body.age_group)
        if body.message_type == "answer" and not context.get("student_answer"):
            context["student_answer"] = body.message
        if body.conversationHistory:
            context["conversation_history"] = body.conversationHistory[-10:]

        response = await TutorHarness().reply(context)
        if user_id is not None:
            course_id = context.get("courseId")
            lesson_id = context.get("lessonId")
            await save_chat_message(db, str(user_id), "user", body.message, course_id, lesson_id, {"topic": body.topic})
            for tutor_message in response.messages:
                await save_chat_message(db, str(user_id), "assistant", tutor_message.content, course_id, lesson_id, {"role": tutor_message.role})
            await db.flush()
        logger.info("四角色辅导完成: user_id=%s, roles=%s", user_id, len(response.messages))
        return success_response(data=response, message="辅导回复生成成功")
    except Exception:
        logger.exception("四角色辅导失败: user_id=%s", user_id)
        fallback = TutorResponse(
            messages=[
                TutorMessage(
                    role="teacher",
                    name="老师",
                    content="暂时没有读懂你的问题，请换一种说法，并告诉我你已经想到哪一步。",
                )
            ],
            suggested_next_step="请用一句话重新描述题目和你的思路。",
            diagnosis="暂时无法完成完整诊断，请换一种说法说明已知条件和你的思路。",
            teaching_strategy={
                "approach": "standard",
                "pace": "normal",
                "focus_area": "题意与条件",
            },
            mastery=0.5,
        )
        return success_response(data=fallback, message="已提供基础辅导提示")


class ExplainQuestionRequest(BaseModel):
    """答题后请求辅导讲解。"""

    question_id: uuid.UUID
    # 兼容已有调用方；答案权限只信任服务端 Answer 记录，绝不使用这两个字段。
    user_answer: Optional[str] = Field(default=None, deprecated=True)
    is_correct: Optional[bool] = Field(default=None, deprecated=True)


@router.post("/explain-question")
async def explain_question_after_answer(
    body: ExplainQuestionRequest,
    user_id: Optional[uuid.UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """返回题目上下文和受诊断策略影响的导师首条回复。"""

    result = await db.execute(
        select(Question)
        .options(joinedload(Question.knowledge_node_rel))
        .where(Question.id == body.question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    verified_answer = None
    if user_id is not None:
        answer_result = await db.execute(
            select(Answer)
            .join(LearningSession, Answer.session_id == LearningSession.id)
            .where(
                Answer.question_id == body.question_id,
                LearningSession.user_id == user_id,
            )
            .order_by(Answer.answered_at.desc())
            .limit(1)
        )
        verified_answer = answer_result.scalar_one_or_none()

    knowledge_point = (
        question.knowledge_node_rel.title
        if question.knowledge_node_rel is not None
        else "相关知识点"
    )
    context = {
        "question": {
            "question_body": question.question_body,
            "knowledge_point": knowledge_point,
        },
        "student_answer": verified_answer.user_answer if verified_answer else None,
        "is_correct": verified_answer.is_correct if verified_answer else None,
        "student_message": (
            "我做对了，想继续理解为什么。"
            if verified_answer is not None and verified_answer.is_correct
            else "请先提示我应该检查哪些条件和关系。"
        ),
        "topic": knowledge_point,
    }
    tutor_response = await TutorHarness().reply(context)
    teacher_reply = next(
        message for message in tutor_response.messages if message.role == "teacher"
    )
    logger.info(
        "答题后辅导生成完成: user_id=%s, question_id=%s",
        user_id,
        body.question_id,
    )
    question_data = {
        "id": str(question.id),
        "text": question.question_body,
        "knowledge_point": knowledge_point,
    }
    if verified_answer is not None:
        question_data.update(
            {
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
            }
        )

    return success_response(
        data={
            "question": question_data,
            "ai_reply": teacher_reply,
            "tutor_response": tutor_response,
            "answer_verified": verified_answer is not None,
        },
        message="题目辅导生成成功",
    )


# ==============================
# 技能管理（审计进化）
# ==============================

@router.get("/skills", response_model=ApiResponse)
async def list_skills(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    技能列表接口（分页）

    查询审计进化系统中的技能列表，支持按名称关键词搜索。

    Args:
        keyword (Optional[str]): 技能名称关键词
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页技能列表
    """
    # 构建查询条件：仅查询活跃技能
    stmt = select(Skill).where(Skill.is_active == True)
    count_stmt = select(func.count()).select_from(Skill).where(Skill.is_active == True)

    # 关键词模糊匹配
    if keyword:
        stmt = stmt.where(Skill.name.ilike(f"%{keyword}%"))
        count_stmt = count_stmt.where(Skill.name.ilike(f"%{keyword}%"))

    # 分页查询
    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(Skill.created_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return paged_response(
        data=[
            {
                "id": str(s.id),
                "name": s.name,
                "version": s.version,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "quality_score_avg": s.quality_score_avg,
                "last_used_at": str(s.last_used_at) if s.last_used_at else None,
            }
            for s in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/skills/{skill_id}", response_model=ApiResponse)
async def get_skill_detail(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    技能详情接口

    根据技能 ID 查询详细信息，包括触发条件、版本、内容、使用统计等。

    Args:
        skill_id (uuid.UUID): 技能 UUID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 技能详情
    """
    # 查询技能详情
    stmt = select(Skill).where(Skill.id == skill_id)
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()

    if skill is None:
        return ApiResponse(code="BIZ_001", message="技能不存在", data=None)

    return success_response(
        data={
            "id": str(skill.id),
            "name": skill.name,
            "trigger_conditions": skill.trigger_conditions,
            "version": skill.version,
            "content": skill.content,
            "success_count": skill.success_count,
            "failure_count": skill.failure_count,
            "quality_score_avg": skill.quality_score_avg,
            "last_used_at": str(skill.last_used_at) if skill.last_used_at else None,
            "is_active": skill.is_active,
        },
        message="获取技能详情成功",
    )


# ==============================
# 用户行为档案（进化相关）
# ==============================

@router.get("/user-profile", response_model=ApiResponse)
async def get_user_behavior_profile(
    user: User = Depends(get_current_user),
):
    """
    获取用户行为档案接口

    返回当前登录用户的行为档案数据，包括积分、连续学习天数、行为模型等。

    Args:
        user (User): 当前登录用户对象

    Returns:
        ApiResponse: 用户行为档案详情
    """
    # 直接从用户对象提取行为档案字段
    return success_response(
        data={
            "id": str(user.id),
            "nickname": user.nickname,
            "age_group": user.age_group,
            "total_score": user.total_score,
            "streak_days": user.streak_days,
            "behavior_profile": user.behavior_profile,
        },
        message="获取用户行为档案成功",
    )


# ==============================
# 进化记录
# ==============================

@router.get("/evolution-log", response_model=ApiResponse)
async def list_evolution_records(
    evolution_type: Optional[str] = Query(None, description="进化类型"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    进化记录列表接口（分页）

    查询审计进化系统的进化记录，支持按进化类型筛选。

    Args:
        evolution_type (Optional[str]): 进化类型筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页进化记录列表
    """
    # 构建查询条件
    stmt = select(EvolutionRecord)
    count_stmt = select(func.count()).select_from(EvolutionRecord)

    if evolution_type:
        stmt = stmt.where(EvolutionRecord.evolution_type == evolution_type)
        count_stmt = count_stmt.where(EvolutionRecord.evolution_type == evolution_type)

    # 分页查询
    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(EvolutionRecord.created_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return paged_response(
        data=[
            {
                "id": str(r.id),
                "evolution_type": r.evolution_type,
                "trigger_reason": r.trigger_reason,
                "target_name": r.target_name,
                "quality_before": r.quality_before,
                "quality_after": r.quality_after,
                "rolled_back": r.rolled_back,
                "created_at": str(r.created_at),
            }
            for r in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ==============================
# 错误日志
# ==============================

@router.get("/error-log", response_model=ApiResponse)
async def list_error_logs(
    error_type: Optional[str] = Query(None, description="错误类型"),
    severity: Optional[str] = Query(None, description="严重度"),
    agent_name: Optional[str] = Query(None, description="Agent 名称"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    错误日志列表接口（分页）

    查询审计进化系统的错误日志，支持按错误类型、严重度、Agent 名称筛选。

    Args:
        error_type (Optional[str]): 错误类型筛选
        severity (Optional[str]): 严重度筛选
        agent_name (Optional[str]): Agent 名称筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页错误日志列表
    """
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可以查看错误日志")

    # 构建动态查询条件
    stmt = select(ErrorLog)
    count_stmt = select(func.count()).select_from(ErrorLog)

    if error_type:
        stmt = stmt.where(ErrorLog.error_type == error_type)
        count_stmt = count_stmt.where(ErrorLog.error_type == error_type)
    if severity:
        stmt = stmt.where(ErrorLog.severity == severity)
        count_stmt = count_stmt.where(ErrorLog.severity == severity)
    if agent_name:
        stmt = stmt.where(ErrorLog.agent_name == agent_name)
        count_stmt = count_stmt.where(ErrorLog.agent_name == agent_name)

    # 分页查询
    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(ErrorLog.created_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return paged_response(
        data=[
            {
                "id": str(e.id),
                "agent_name": e.agent_name,
                "step_name": e.step_name,
                "error_type": e.error_type,
                "error_code": e.error_code,
                "severity": e.severity,
                "raw_error": e.raw_error,
                "routing_target": e.routing_target,
                "auto_fix_attempted": e.auto_fix_attempted,
                "created_at": str(e.created_at),
            }
            for e in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ==============================
# 会话记忆
# ==============================

@router.get("/memories", response_model=ApiResponse)
async def list_session_memories(
    user_id: uuid.UUID = Depends(get_current_user_id),
    memory_type: Optional[str] = Query(None, description="记忆类型"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    用户会话记忆列表接口（分页）

    查询当前用户的会话记忆，支持按记忆类型筛选。

    Args:
        user_id (uuid.UUID): 当前登录用户 ID
        memory_type (Optional[str]): 记忆类型筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页会话记忆列表
    """
    # 构建查询条件：限定当前用户
    stmt = select(SessionMemory).where(SessionMemory.user_id == user_id)
    count_stmt = select(func.count()).select_from(SessionMemory).where(
        SessionMemory.user_id == user_id
    )

    # 记忆类型筛选
    if memory_type:
        stmt = stmt.where(SessionMemory.memory_type == memory_type)
        count_stmt = count_stmt.where(SessionMemory.memory_type == memory_type)

    # 分页查询
    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(SessionMemory.created_at.desc())
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return paged_response(
        data=[
            {
                "id": str(m.id),
                "memory_type": m.memory_type,
                "content": m.content,
                "confidence": m.confidence,
                "related_topic": m.related_topic,
                "expires_at": str(m.expires_at),
                "is_expired": m.is_expired,
            }
            for m in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
