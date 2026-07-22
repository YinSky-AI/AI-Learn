# -*- coding: utf-8 -*-
"""
内容服务模块

提供知识库内容的查询与筛选业务逻辑，包括年龄分级、学科、知识点、题目等。
所有接口均为公开查询，无需用户认证。

主要功能：
    - 年龄分级与学科列表查询
    - 知识点分页查询（支持多条件筛选）
    - 知识点详情与关联题目查询
"""

import uuid
from typing import Any, List, Optional

from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AI_LearnAsyncSessionLocal
from app.models.content import AgeGroup, Subject, KnowledgeNode, Question

# ---------------------------------------------------------------------------
# ai_learn ↔ learning_platform 字段映射
# ---------------------------------------------------------------------------

_SUBJECT_CODE_TO_AI = {
    "SUBJ_MATH": "math",
    "SUBJ_CHINESE": "chinese",
    "SUBJ_ENGLISH": "english",
    "SUBJ_PHYSICS": "physics",
    "SUBJ_CHEMISTRY": "chemistry",
    "SUBJ_BIOLOGY": "biology",
    "SUBJ_HISTORY": "history",
    "SUBJ_GEOGRAPHY": "geography",
    "SUBJ_POLITICS": "politics",
    "SUBJ_SCIENCE": "science",
    "SUBJ_ART": "art",
    "SUBJ_PROGRAMMING": "programming",
}

_AGE_GROUP_CODE_TO_AI = {
    "AGE_06_08": "6-8",
    "AGE_09_11": "9-12",
    "AGE_12_14": "13-15",
    "AGE_15_18": "16-18",
}

_DIFFICULTY_TO_AI = {
    "DIFF_EASY": "beginner",
    "DIFF_MEDIUM": "intermediate",
    "DIFF_HARD": "advanced",
}

_DIFFICULTY_FROM_AI = {
    "beginner": "DIFF_EASY",
    "intermediate": "DIFF_MEDIUM",
    "advanced": "DIFF_HARD",
}

# ai_learn 的 type 有多种写法，统一映射到 learning_platform 的题型
# 判断题、简答题等 learning_platform 不支持，直接跳过
_AI_TYPE_TO_LP = {
    "单选题": "CHOICE",
    "single_choice": "CHOICE",
    "单选": "CHOICE",
    "多选题": "MULTIPLE_CHOICE",
    "multiple_choice": "MULTIPLE_CHOICE",
    "多选": "MULTIPLE_CHOICE",
    "填空题": "FILL_BLANK",
    "fill_blank": "FILL_BLANK",
    "填空": "FILL_BLANK",
}


def _question_value(question: Any, field: str) -> Any:
    """同时读取 ORM 对象和映射字典中的题目字段。"""
    return question.get(field) if isinstance(question, dict) else getattr(question, field, None)


def is_question_practice_ready(question: Any) -> bool:
    """判断题目是否具备可展示、可提交且可由服务端判定的完整结构。"""
    question_type = str(_question_value(question, "question_type") or "").strip().upper()
    question_body = str(_question_value(question, "question_body") or "").strip()
    correct_answer = str(_question_value(question, "correct_answer") or "").strip()
    if not question_body or not correct_answer:
        return False
    if question_type == "FILL_BLANK":
        return True
    if question_type not in {"CHOICE", "MULTIPLE_CHOICE"}:
        return False

    options = _question_value(question, "options")
    if not isinstance(options, list) or len(options) < 2:
        return False

    keys = []
    for option in options:
        if not isinstance(option, dict):
            return False
        key = str(option.get("key") or "").strip().upper()
        value = str(option.get("value") or "").strip()
        if not key or not value or key in keys:
            return False
        keys.append(key)

    answer_keys = {
        part.strip().upper()
        for part in correct_answer.replace("，", ",").split(",")
        if part.strip()
    }
    if not answer_keys or not answer_keys.issubset(set(keys)):
        return False
    return question_type == "MULTIPLE_CHOICE" or len(answer_keys) == 1


def _uuid_from_ai_id(ai_id: int) -> uuid.UUID:
    """把 ai_learn 的 integer ID 转成稳定的 UUID"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"ai_learn_question_{ai_id}")


def _options_from_ai(ai_options: Any) -> Optional[List[dict]]:
    """把 ai_learn 的选项格式转为 learning_platform 格式 [{key, value}]"""
    if not ai_options:
        return None
    result = []
    for opt in ai_options:
        if not isinstance(opt, dict):
            continue
        # ai_learn 中 options 有的用 "label" 有的用 "key"
        label = str(opt.get("label") or opt.get("key", "")).strip()
        text = str(opt.get("text", "")).strip()
        if not label:
            continue
        # 清理 text 中可能的 "A. " 前缀
        prefix = f"{label}. "
        if text.startswith(prefix):
            text = text[len(prefix):]
        result.append({"key": label, "value": text})
    return result if result else None


async def _fetch_questions_from_ai_learn(
    subject_code: Optional[str] = None,
    age_group_code: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    question_type: Optional[str] = None,
    knowledge_node_id: Optional[uuid.UUID] = None,
    limit: int = 50,
) -> List[dict]:
    """
    从 ai_learn 数据库获取题目，并映射为 learning_platform 的 dict 格式。

    返回的 dict 可直接被 QuestionResponse.model_validate() 序列化。
    """
    async with AI_LearnAsyncSessionLocal() as ai_db:
        conditions = ["deleted_at IS NULL"]
        params: dict = {}

        if subject_code and subject_code in _SUBJECT_CODE_TO_AI:
            conditions.append("subject = :subject")
            params["subject"] = _SUBJECT_CODE_TO_AI[subject_code]

        if age_group_code and age_group_code in _AGE_GROUP_CODE_TO_AI:
            conditions.append("age_group = :age_group")
            params["age_group"] = _AGE_GROUP_CODE_TO_AI[age_group_code]

        if difficulty_level and difficulty_level in _DIFFICULTY_TO_AI:
            conditions.append("difficulty = :difficulty")
            params["difficulty"] = _DIFFICULTY_TO_AI[difficulty_level]

        # 题型过滤：先按 learning_platform 的 type 映射为 ai_learn 的 type 列表
        if question_type:
            reverse_types = [k for k, v in _AI_TYPE_TO_LP.items() if v == question_type]
            if reverse_types:
                placeholders = ", ".join([f":t{i}" for i in range(len(reverse_types))])
                conditions.append(f"type IN ({placeholders})")
                for i, t in enumerate(reverse_types):
                    params[f"t{i}"] = t
            else:
                return []  # 无匹配的 ai_learn 题型

        where_clause = " AND ".join(conditions)

        sql = text(f"""
            SELECT id, subject, age_group, difficulty, type,
                   content, options, correct_answer, explanation
            FROM questions
            WHERE {where_clause}
            ORDER BY id
            LIMIT :limit
        """)
        params["limit"] = limit

        result = await ai_db.execute(sql, params)
        rows = result.mappings().all()

        mapped: List[dict] = []
        for row in rows:
            ai_type = row["type"]
            lp_type = _AI_TYPE_TO_LP.get(ai_type)
            if lp_type is None:
                continue  # 跳过 learning_platform 不支持的题型

            mapped.append({
                "id": _uuid_from_ai_id(row["id"]),
                "knowledge_node_id": knowledge_node_id,
                "difficulty_level": _DIFFICULTY_FROM_AI.get(row["difficulty"], "DIFF_MEDIUM"),
                "question_type": lp_type,
                "question_body": row["content"],
                "options": _options_from_ai(row["options"]),
                "correct_answer": row["correct_answer"],
                "explanation": row["explanation"],
                "standard_time_seconds": 30,
                "sort_order": 0,
            })

        return mapped


async def _count_questions_in_ai_learn(
    subject_code: Optional[str] = None,
    age_group_code: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    question_type: Optional[str] = None,
) -> int:
    """从 ai_learn 统计符合条件的题目数"""
    async with AI_LearnAsyncSessionLocal() as ai_db:
        conditions = ["deleted_at IS NULL"]
        params: dict = {}

        if subject_code and subject_code in _SUBJECT_CODE_TO_AI:
            conditions.append("subject = :subject")
            params["subject"] = _SUBJECT_CODE_TO_AI[subject_code]

        if age_group_code and age_group_code in _AGE_GROUP_CODE_TO_AI:
            conditions.append("age_group = :age_group")
            params["age_group"] = _AGE_GROUP_CODE_TO_AI[age_group_code]

        if difficulty_level and difficulty_level in _DIFFICULTY_TO_AI:
            conditions.append("difficulty = :difficulty")
            params["difficulty"] = _DIFFICULTY_TO_AI[difficulty_level]

        if question_type:
            reverse_types = [k for k, v in _AI_TYPE_TO_LP.items() if v == question_type]
            if reverse_types:
                placeholders = ", ".join([f":t{i}" for i in range(len(reverse_types))])
                conditions.append(f"type IN ({placeholders})")
                for i, t in enumerate(reverse_types):
                    params[f"t{i}"] = t
            else:
                return 0

        where_clause = " AND ".join(conditions)
        sql = text(f"SELECT COUNT(*) FROM questions WHERE {where_clause}")
        result = await ai_db.execute(sql, params)
        return result.scalar() or 0


# ============ 年龄分级 ============

async def get_all_age_groups(db: AsyncSession) -> List[AgeGroup]:
    """
    获取所有年龄分级

    Args:
        db (AsyncSession): 异步数据库会话

    Returns:
        List[AgeGroup]: 按最小年龄排序的年龄分级列表
    """
    stmt = select(AgeGroup).order_by(AgeGroup.min_age)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_age_group_by_code(db: AsyncSession, code: str) -> Optional[AgeGroup]:
    """
    根据编码获取年龄分级

    Args:
        db (AsyncSession): 异步数据库会话
        code (str): 年龄分级编码

    Returns:
        Optional[AgeGroup]: 年龄分级对象，不存在返回 None
    """
    stmt = select(AgeGroup).where(AgeGroup.code == code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ============ 学科 ============

async def get_all_subjects(db: AsyncSession) -> List[Subject]:
    """
    获取所有学科

    Args:
        db (AsyncSession): 异步数据库会话

    Returns:
        List[Subject]: 按排序号排列的学科列表
    """
    stmt = select(Subject).order_by(Subject.sort_order)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_subject_by_code(db: AsyncSession, code: str) -> Optional[Subject]:
    """
    根据编码获取学科

    Args:
        db (AsyncSession): 异步数据库会话
        code (str): 学科编码

    Returns:
        Optional[Subject]: 学科对象，不存在返回 None
    """
    stmt = select(Subject).where(Subject.code == code)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ============ 知识点 ============

async def get_knowledge_node_by_id(
    db: AsyncSession,
    node_id: uuid.UUID,
) -> Optional[KnowledgeNode]:
    """
    根据 ID 获取知识点

    Args:
        db (AsyncSession): 异步数据库会话
        node_id (uuid.UUID): 知识点 UUID

    Returns:
        Optional[KnowledgeNode]: 知识点对象，不存在返回 None
    """
    stmt = select(KnowledgeNode).where(KnowledgeNode.id == node_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_knowledge_nodes(
    db: AsyncSession,
    subject_code: Optional[str] = None,
    age_group_code: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    content_type: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    分页查询知识点列表（支持多条件筛选）

    Args:
        db (AsyncSession): 异步数据库会话
        subject_code (Optional[str]): 学科编码筛选
        age_group_code (Optional[str]): 年龄分级编码筛选
        difficulty_level (Optional[str]): 难度等级筛选
        content_type (Optional[str]): 内容类型筛选
        keyword (Optional[str]): 标题或描述关键词搜索
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 20

    Returns:
        dict: 分页知识点列表
    """
    stmt = select(KnowledgeNode).where(KnowledgeNode.is_active == True)
    count_stmt = select(func.count()).select_from(KnowledgeNode).where(
        KnowledgeNode.is_active == True
    )

    # 条件筛选：学科、年龄分级、难度、内容类型
    if subject_code:
        stmt = stmt.where(KnowledgeNode.subject_code == subject_code)
        count_stmt = count_stmt.where(KnowledgeNode.subject_code == subject_code)
    if age_group_code:
        stmt = stmt.where(KnowledgeNode.age_group_code == age_group_code)
        count_stmt = count_stmt.where(KnowledgeNode.age_group_code == age_group_code)
    if difficulty_level:
        stmt = stmt.where(KnowledgeNode.difficulty_level == difficulty_level)
        count_stmt = count_stmt.where(KnowledgeNode.difficulty_level == difficulty_level)
    if content_type:
        stmt = stmt.where(KnowledgeNode.content_type == content_type)
        count_stmt = count_stmt.where(KnowledgeNode.content_type == content_type)
    # 关键词模糊匹配（标题 + 描述）
    if keyword:
        search_filter = or_(
            KnowledgeNode.title.ilike(f"%{keyword}%"),
            KnowledgeNode.description.ilike(f"%{keyword}%"),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    # 排序：先按 sort_order 再按创建时间
    stmt = stmt.order_by(KnowledgeNode.sort_order, KnowledgeNode.created_at)

    # 查询总数
    total = (await db.execute(count_stmt)).scalar()

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    return {
        "items": nodes,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============ 题目 ============

async def get_question_by_id(
    db: AsyncSession,
    question_id: uuid.UUID,
) -> Optional[Question]:
    """
    根据 ID 获取题目

    Args:
        db (AsyncSession): 异步数据库会话
        question_id (uuid.UUID): 题目 UUID

    Returns:
        Optional[Question]: 题目对象，不存在返回 None
    """
    stmt = select(Question).where(Question.id == question_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_questions_by_node(
    db: AsyncSession,
    knowledge_node_id: uuid.UUID,
    difficulty_level: Optional[str] = None,
    question_type: Optional[str] = None,
    local_only: bool = False,
) -> List[dict]:
    """
    获取某知识点下的题目列表（优先从 ai_learn 题库查询，fallback 到本地）

    先通过 learning_platform 的 KnowledgeNode 获取学科/年龄段/难度元数据，
    再映射到 ai_learn 的字段进行查询。若 ai_learn 无匹配题目，则回退到
    learning_platform 本地 questions 表。

    Args:
        db (AsyncSession): 异步数据库会话
        knowledge_node_id (uuid.UUID): 知识点 UUID
        difficulty_level (Optional[str]): 难度等级筛选
        question_type (Optional[str]): 题型筛选
        local_only (bool): 仅查询主业务库。需要通过学习会话提交答案时必须启用，
            避免返回外部题库中无法由主库判题的题目 ID。

    Returns:
        List[dict]: 题目 dict 列表，可直接被 QuestionResponse.model_validate
    """
    node = await get_knowledge_node_by_id(db, knowledge_node_id)
    if node is None:
        return []

    effective_difficulty = difficulty_level or node.difficulty_level

    # 1. 普通内容浏览优先查 ai_learn；交互式答题必须使用主业务库中的题目，
    # 因为学习会话、判题、错题本和行为报告都以主库 questions.id 为外键。
    if not local_only:
        items = await _fetch_questions_from_ai_learn(
            subject_code=node.subject_code,
            age_group_code=node.age_group_code,
            difficulty_level=effective_difficulty,
            question_type=question_type,
            knowledge_node_id=knowledge_node_id,
            limit=50,
        )
        if items:
            return items

    # 2. Fallback：查 learning_platform 本地 questions 表
    stmt = select(Question).where(Question.knowledge_node_id == knowledge_node_id)
    if effective_difficulty:
        stmt = stmt.where(Question.difficulty_level == effective_difficulty)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    stmt = stmt.order_by(Question.sort_order)
    result = await db.execute(stmt)
    local_questions = list(result.scalars().all())

    # 转换为 dict 以便统一返回格式
    mapped = []
    for q in local_questions:
        mapped.append({
            "id": q.id,
            "knowledge_node_id": q.knowledge_node_id,
            "difficulty_level": q.difficulty_level,
            "question_type": q.question_type,
            "question_body": q.question_body,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "standard_time_seconds": q.standard_time_seconds,
            "sort_order": q.sort_order,
        })
    return [question for question in mapped if is_question_practice_ready(question)] if local_only else mapped


async def list_all_questions(
    db: AsyncSession,
    subject_code: Optional[str] = None,
    age_group_code: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    question_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> List[dict]:
    """
    获取全部题目列表（优先从 ai_learn 题库查询，fallback 到本地）

    Args:
        db (AsyncSession): 异步数据库会话（fallback 时使用）
        subject_code (Optional[str]): 学科编码筛选
        age_group_code (Optional[str]): 年龄段编码筛选
        difficulty_level (Optional[str]): 难度筛选
        question_type (Optional[str]): 题型筛选
        limit (int): 每页数量
        offset (int): 偏移量

    Returns:
        List[dict]: 题目 dict 列表，可直接被 QuestionResponse.model_validate
    """
    # 1. 优先查 ai_learn
    items = await _fetch_questions_from_ai_learn(
        subject_code=subject_code,
        age_group_code=age_group_code,
        difficulty_level=difficulty_level,
        question_type=question_type,
        limit=limit + offset,
    )
    if items:
        return items[offset:offset + limit]

    # 2. Fallback：查 learning_platform 本地 questions 表
    stmt = select(Question).join(KnowledgeNode)
    if subject_code:
        stmt = stmt.where(KnowledgeNode.subject_code == subject_code)
    if age_group_code:
        stmt = stmt.where(KnowledgeNode.age_group_code == age_group_code)
    if difficulty_level:
        stmt = stmt.where(Question.difficulty_level == difficulty_level)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    stmt = stmt.order_by(Question.sort_order).offset(offset).limit(limit)
    result = await db.execute(stmt)
    local_questions = list(result.scalars().all())

    mapped = []
    for q in local_questions:
        mapped.append({
            "id": q.id,
            "knowledge_node_id": q.knowledge_node_id,
            "difficulty_level": q.difficulty_level,
            "question_type": q.question_type,
            "question_body": q.question_body,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "standard_time_seconds": q.standard_time_seconds,
            "sort_order": q.sort_order,
        })
    return mapped


async def count_all_questions(
    db: AsyncSession,
    subject_code: Optional[str] = None,
    age_group_code: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    question_type: Optional[str] = None,
) -> int:
    """
    统计符合条件的题目总数（优先从 ai_learn 统计，fallback 到本地）

    Args:
        db (AsyncSession): 异步数据库会话（fallback 时使用）
        subject_code (Optional[str]): 学科编码筛选
        age_group_code (Optional[str]): 年龄段编码筛选
        difficulty_level (Optional[str]): 难度筛选
        question_type (Optional[str]): 题型筛选

    Returns:
        int: 总数
    """
    # 1. 优先统计 ai_learn
    ai_count = await _count_questions_in_ai_learn(
        subject_code=subject_code,
        age_group_code=age_group_code,
        difficulty_level=difficulty_level,
        question_type=question_type,
    )
    if ai_count > 0:
        return ai_count

    # 2. Fallback：统计 learning_platform 本地
    stmt = select(func.count(Question.id)).join(KnowledgeNode)
    if subject_code:
        stmt = stmt.where(KnowledgeNode.subject_code == subject_code)
    if age_group_code:
        stmt = stmt.where(KnowledgeNode.age_group_code == age_group_code)
    if difficulty_level:
        stmt = stmt.where(Question.difficulty_level == difficulty_level)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    result = await db.execute(stmt)
    return result.scalar() or 0
