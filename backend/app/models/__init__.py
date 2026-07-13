# -*- coding: utf-8 -*-
"""
SQLAlchemy 模型包初始化
声明 Base 并导出所有模型
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    SQLAlchemy 声明式基类
    所有模型都继承此基类
    """
    pass


# 导出所有模型（确保 Alembic 能检测到）
from app.models.user import User  # noqa: E402, F401
from app.models.content import AgeGroup, Subject, KnowledgeNode, Question  # noqa: E402, F401
from app.models.learning import LearningSession, Answer  # noqa: E402, F401
from app.models.achievement import Achievement, UserAchievement  # noqa: E402, F401
from app.models.ai_generated import (  # noqa: E402, F401
    GeneratedQuestionBatch,
    GeneratedQuestion,
    QuestionQualityCheck,
    HarnessRun,
    ToolCallLog,
    Skill,
    SessionMemory,
    ErrorLog,
    EvolutionRecord,
)
from app.models.course import (  # noqa: E402, F401
    Course,
    Lesson,
    UserCourse,
    UserLesson,
    ChatMessage,
)

__all__ = [
    "Base",
    "User",
    "AgeGroup",
    "Subject",
    "KnowledgeNode",
    "Question",
    "LearningSession",
    "Answer",
    "Achievement",
    "UserAchievement",
    "GeneratedQuestionBatch",
    "GeneratedQuestion",
    "QuestionQualityCheck",
    "HarnessRun",
    "ToolCallLog",
    "Skill",
    "SessionMemory",
    "ErrorLog",
    "EvolutionRecord",
    "Course",
    "Lesson",
    "UserCourse",
    "UserLesson",
    "ChatMessage",
]
