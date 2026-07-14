# -*- coding: utf-8 -*-
"""
AI 助手与审计进化 API 模块

提供 AI 智能辅导、流式对话、错题分析、技能管理、进化记录查询、错误日志查询等接口。
部分接口支持可选认证，未登录用户也可使用基础 AI 聊天功能。

主要功能：
    - AI 题目解析（占位）
    - SSE 流式 AI 对话（支持上下文与多轮对话）
    - 错题分析（占位）
    - 技能列表与详情查询（审计进化）
    - 用户行为档案查询
    - 进化记录与错误日志查询
    - 用户会话记忆查询
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import get_ai_provider
from app.core.database import get_db
from app.core.deps import get_current_user_id, get_current_user, get_current_user_id_optional
from app.models.ai_generated import Skill, SessionMemory, ErrorLog, EvolutionRecord, HarnessRun
from app.models.user import User
from app.schemas.common import ApiResponse, paged_response, success_response
from app.services import course_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ==============================
# Chat 端点请求/响应模型
# ==============================

class ChatRequest(BaseModel):
    """AI 聊天请求"""
    message: str = Field(..., min_length=1, description="用户消息")
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="上下文信息，可包含 courseId, lessonId, subject, ageGroup 等",
    )
    conversationHistory: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="对话历史，格式为 [{role, content}, ...]",
    )


class ChatResponse(BaseModel):
    """AI 聊天响应"""
    reply: str = Field(..., description="AI 回复内容")
    suggestions: Optional[List[str]] = Field(default=None, description="推荐的后续问题")


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
# 通用 AI 聊天
# ==============================

def _build_system_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    根据 context 构建适配不同年龄段和学科的 system prompt

    Args:
        context: 上下文字典，可包含 subject, ageGroup, courseId, lessonId 等

    Returns:
        构建好的 system prompt 字符串
    """
    subject = ""
    age_group = ""
    course_id = ""
    lesson_id = ""

    if context:
        subject = context.get("subject", "")
        age_group = context.get("ageGroup", "")
        course_id = context.get("courseId", "")
        lesson_id = context.get("lessonId", "")

    # 根据年龄段适配语气和表达方式
    if age_group in ("6-8", "小学低年级"):
        tone = (
            "你说话要非常温柔、亲切，像一个耐心的小学老师。"
            "使用简单易懂的词语，多用比喻和例子来解释概念。"
            "多用鼓励性的语言，避免使用复杂的术语。"
            "回答要简短有趣，可以适当使用拟人化、小故事等方式。"
        )
    elif age_group in ("9-11", "小学高年级"):
        tone = (
            "你说话要友好、耐心，像一个善于引导的辅导老师。"
            "使用清晰易懂的语言，适当引入简单的专业术语并加以解释。"
            "可以通过类比和实际生活中的例子来帮助学生理解。"
            "回答要有逻辑性但不过于学术，鼓励学生思考。"
        )
    elif age_group in ("12-14", "初中"):
        tone = (
            "你说话要专业但不生硬，像一个知识渊博的学长。"
            "可以使用适当的专业术语，但要确保解释清楚。"
            "注重知识点的深度和逻辑推理，引导学生建立知识体系。"
            "鼓励批判性思维，可以提出引导性的反问。"
        )
    elif age_group in ("15-18", "高中"):
        tone = (
            "你说话要专业、严谨，像一个大学教授。"
            "可以使用专业术语和抽象概念，注重深度分析。"
            "回答要有深度和广度，可以涉及前沿知识和跨学科联系。"
            "鼓励独立思考和深入研究。"
        )
    else:
        tone = (
            "你说话要清晰、友好，像一个乐于助人的学习助手。"
            "根据用户的问题提供准确的解答，语言通俗易懂。"
            "注重解释的逻辑性，适当使用例子辅助说明。"
        )

    # 学科相关指导
    subject_guide = ""
    if subject:
        subject_guide = f"\n当前学科：{subject}。请围绕该学科知识进行回答。"

    # 课程/课时上下文
    course_guide = ""
    if course_id:
        course_guide = f"\n当前课程 ID：{course_id}。"
    if lesson_id:
        course_guide += f"\n当前课时 ID：{lesson_id}。请结合当前课时内容回答。"

    system_prompt = (
        f"你是一个智能学习助手，专门帮助学生学习各科知识。\n\n"
        f"## 语气与风格要求\n{tone}\n\n"
        f"## 回答要求\n"
        f"- 回答要准确、有条理\n"
        f"- 如果不确定答案，请诚实说明\n"
        f"- 适当给出学习建议和相关的知识点扩展"
        f"{subject_guide}{course_guide}\n"
    )

    return system_prompt


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user_id: Optional[uuid.UUID] = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    通用 AI 聊天接口（SSE 流式输出）

    接收用户消息，调用 DeepSeek AI 模型以 SSE 流式方式返回回复。
    支持可选认证（未登录用户也可使用）。
    支持传入上下文信息以适配不同学科和年龄段。
    支持传入对话历史以实现多轮对话。
    调用成功后自动保存对话记录到 ChatMessage 表。

    Args:
        body (ChatRequest): 聊天请求体（消息、上下文、对话历史）
        user_id (Optional[uuid.UUID]): 当前登录用户 ID（可选认证）
        db (AsyncSession): 异步数据库会话

    Returns:
        StreamingResponse: SSE 流式响应，包含 AI 回复片段与结束事件
    """
    # 构建 system prompt（根据学科与年龄段适配语气）
    system_prompt = _build_system_prompt(body.context)

    # 组装 messages 列表：system + 历史消息 + 当前用户消息
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    # 追加对话历史（限制最近 20 条，防止 token 过长）
    if body.conversationHistory:
        recent_history = body.conversationHistory[-20:]
        for turn in recent_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # 追加当前用户消息
    messages.append({"role": "user", "content": body.message})

    # 提取上下文中的课程/课时 ID（保持字符串格式）
    context = body.context or {}
    course_id = None
    lesson_id = None
    try:
        raw_course = context.get("courseId")
        raw_lesson = context.get("lessonId")
        if raw_course:
            course_id = str(raw_course)
        if raw_lesson:
            lesson_id = str(raw_lesson)
    except (ValueError, TypeError):
        pass

    async def event_stream():
        """内部 SSE 流生成器：逐块返回 AI 回复并在结束后保存记录。"""
        try:
            provider = get_ai_provider()
            full_reply = ""

            # 逐块流式生成并 yield SSE 事件
            async for chunk in provider.generate_stream(messages=messages):
                full_reply += chunk
                # SSE 格式：data: {"content": "..."}\n\n
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

            # 流结束后发送结束事件，包含完整回复和 suggestions
            suggestions = _generate_suggestions(body.message, body.context)
            yield f"data: {json.dumps({'done': True, 'reply': full_reply, 'suggestions': suggestions}, ensure_ascii=False)}\n\n"

            logger.info(
                f"AI Chat 流式完成: user_id={user_id}, "
                f"reply_length={len(full_reply)}"
            )

            # 异步保存聊天记录（不阻塞流）
            try:
                await course_service.save_chat_message(
                    db,
                    user_id=user_id,
                    role="user",
                    content=body.message,
                    course_id=course_id,
                    lesson_id=lesson_id,
                    context=context,
                )
                await course_service.save_chat_message(
                    db,
                    user_id=user_id,
                    role="assistant",
                    content=full_reply,
                    course_id=course_id,
                    lesson_id=lesson_id,
                    context=context,
                )
            except Exception as save_err:
                logger.warning(f"保存聊天记录失败: {save_err}")

        except Exception as e:
            logger.error(f"AI Chat 流式调用失败: user_id={user_id}, error={e}")
            error_msg = "抱歉，AI 助手暂时无法回答您的问题，请稍后再试。"
            yield f"data: {json.dumps({'error': True, 'content': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _generate_suggestions(
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    根据用户消息和上下文生成推荐后续问题

    简单实现：基于学科和消息关键词返回通用建议
    """
    suggestions: List[str] = []
    subject = ""

    if context:
        subject = context.get("subject", "")

    # 通用学习建议
    if subject:
        suggestions.append(f"帮我复习一下{subject}的重点知识")
        suggestions.append(f"给我出一道{subject}的练习题")
    else:
        suggestions.append("你能给我举个例子吗？")
        suggestions.append("请用更简单的方式解释一下")

    suggestions.append("我还有其他问题想问")

    return suggestions[:3]


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
