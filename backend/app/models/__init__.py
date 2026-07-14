# -*- coding: utf-8 -*-
"""
SQLAlchemy 模型包初始化模块

声明 SQLAlchemy 声明式基类 Base，并导出所有数据模型类，
确保 Alembic 迁移工具和 SQLAlchemy 的 metadata 能正确发现所有表定义。

模型按业务域组织为多个模块：
- user: 用户相关模型
- course: 课程、课时及用户学习进度模型
- content: 知识点、学科、年龄分级、题目模型
- learning: 学习会话和答题记录模型
- achievement: 成就和用户成就模型
- ai_generated: AI 生成题目、质量检查、Harness 执行记录等模型
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    SQLAlchemy 声明式基类

    所有 ORM 数据模型均直接或间接继承此类。
    DeclarativeBase 提供声明式映射支持，使得通过类定义即可创建表结构。

    Note:
        该基类不包含通用字段（如 id、created_at），这些由 database.BaseModel 提供。
        实际模型通常同时继承 BaseModel 和 Base：
        `class MyModel(BaseModel, Base): ...`
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
