"""题目公开、已验证作答与管理场景的唯一序列化边界。"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Mapping
from typing import Any


logger = logging.getLogger(__name__)


class QuestionAccessDenied(PermissionError):
    """调用方没有提供足够的题目访问证明。"""


_SENSITIVE_KEY_NAMES = frozenset(
    {
        "answer",
        "answerexplanation",
        "answerkey",
        "analysis",
        "correctanswer",
        "detailedsolution",
        "explanation",
        "finalanswer",
        "isanswer",
        "iscorrect",
        "modelanswer",
        "rationale",
        "reasoning",
        "referenceanswer",
        "solution",
        "standardanswer",
    }
)


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _is_sensitive_key(value: object) -> bool:
    normalized = _normalized_key(value)
    if normalized in _SENSITIVE_KEY_NAMES:
        return True
    return any(
        marker in normalized
        for marker in (
            "answer",
            "analysis",
            "correct",
            "explanation",
            "rationale",
            "reasoning",
            "solution",
        )
    )


def sanitize_public_value(value: Any) -> Any:
    """递归移除答案、解析及常见等价字段，同时保留无敏感含义的扩展元数据。"""

    if isinstance(value, Mapping):
        return {
            key: sanitize_public_value(nested)
            for key, nested in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_public_value(nested) for nested in value]
    return value


def _question_value(question: object, field: str, default: Any = None) -> Any:
    if isinstance(question, Mapping):
        return question.get(field, default)
    return getattr(question, field, default)


def public_question_brief(question: object) -> dict[str, Any]:
    """只返回学习者展示所需字段，禁止答案通过顶层或嵌套结构泄露。"""

    return {
        "id": _question_value(question, "id"),
        "knowledge_node_id": _question_value(question, "knowledge_node_id"),
        "difficulty_level": _question_value(question, "difficulty_level"),
        "question_type": _question_value(question, "question_type"),
        "question_body": _question_value(question, "question_body"),
        "options": sanitize_public_value(_question_value(question, "options")),
        "standard_time_seconds": _question_value(question, "standard_time_seconds", 0),
        "sort_order": _question_value(question, "sort_order"),
    }


def verified_answer_feedback(
    question: object,
    *,
    verified_question_id: uuid.UUID,
    is_correct: bool,
) -> dict[str, Any]:
    """在上层已核验主体、会话和题目归属后，生成必要的作答反馈。"""

    question_id = _question_value(question, "id")
    if question_id is None or question_id != verified_question_id:
        raise QuestionAccessDenied("题目与已验证作答不匹配")
    return {
        "is_correct": is_correct,
        "correct_answer": _question_value(question, "correct_answer"),
        "explanation": _question_value(question, "explanation"),
    }


def admin_question_full(
    question: object,
    *,
    is_authorized: bool,
    actor_id: uuid.UUID,
    reason: str,
) -> dict[str, Any]:
    """管理员 Adapter；调用方必须先完成会话和权限校验，并提供审计上下文。"""

    if not is_authorized or not actor_id or not reason.strip():
        raise QuestionAccessDenied("缺少管理员题目访问授权")
    question_id = _question_value(question, "id")
    logger.info(
        "管理员读取完整题目: actor_id=%s question_id=%s reason=%s",
        actor_id,
        question_id,
        reason,
    )
    return {
        **public_question_brief(question),
        "correct_answer": _question_value(question, "correct_answer"),
        "explanation": _question_value(question, "explanation"),
    }
