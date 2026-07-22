# -*- coding: utf-8 -*-
"""
课程与课时模型定义模块

定义课程（Course）、课时（Lesson）、用户课程关联（UserCourse）、
用户课时记录（UserLesson）和 AI 对话历史（ChatMessage）数据模型。

该模块支撑平台的核心学习流程：
- 课程管理：课程信息的创建、查询和展示
- 课时编排：课时在课程内的顺序组织和内容管理
- 学习进度追踪：记录用户课程和课时的完成状态
- AI 辅导对话：存储用户与 AI 助教的多轮对话历史
"""

from typing import List, Optional

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    Float,
    JSON,
    Index,
    UniqueConstraint,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.models import Base


class Course(BaseModel, Base):
    """
    课程模型

    定义平台课程的基本信息、分类属性和关联关系。
    课程是课时的容器，通过 subject、age_group、difficulty 等维度进行分类。

    Attributes:
        title: 课程标题
        description: 课程描述（富文本）
        subject: 学科分类（如 math、chinese）
        age_group: 适用年龄段编码
        difficulty: 难度等级（beginner/intermediate/advanced）
        duration: 课程总时长（分钟）
        rating: 课程评分（默认 4.0）
        enroll_count: 报名人数统计
        image_url: 封面图 URL
        total_lessons: 总课时数
        tags: 标签列表（JSON 数组）
        is_active: 是否上架启用
        sort_order: 排序权重
        slug: URL 友好标识符
        lessons: 关联的课时列表（一对多）
        user_courses: 用户学习记录列表（一对多）
    """

    __tablename__ = "courses"

    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="课程标题")
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="课程描述"
    )
    subject: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="学科"
    )
    age_group: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="年龄段"
    )
    difficulty: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, comment="难度: beginner/intermediate/advanced"
    )
    duration: Mapped[int] = mapped_column(
        Integer, default=0, comment="课程总时长(分钟)"
    )
    rating: Mapped[float] = mapped_column(
        Float, default=4.0, comment="评分"
    )
    enroll_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="报名人数"
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="封面图URL"
    )
    total_lessons: Mapped[int] = mapped_column(
        Integer, default=0, comment="总课时数"
    )
    tags: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="标签列表"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序权重"
    )
    slug: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True, comment="URL标识"
    )

    # 关系
    lessons: Mapped[List["Lesson"]] = relationship(
        "Lesson", back_populates="course", lazy="selectin", cascade="all, delete-orphan"
    )
    user_courses: Mapped[List["UserCourse"]] = relationship(
        "UserCourse", back_populates="course", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_courses_subject_difficulty", "subject", "difficulty"),
        Index("ix_courses_active", "is_active"),
    )


class Lesson(BaseModel, Base):
    """
    课时模型

    定义课程内的具体学习单元，支持多种内容类型（视频、文本、互动、测验、游戏）。
    课时通过 order 字段在课程内排序，通过 course_id 关联所属课程。

    Attributes:
        course_id: 所属课程 ID（外键，级联删除）
        title: 课时标题
        description: 课时描述
        type: 内容类型（video/text/interactive/quiz/game）
        duration: 课时时长（分钟）
        order: 在课程内的展示顺序
        content: 课时内容（富文本/Markdown）
        is_active: 是否启用
        course: 关联的课程对象（多对一）
        user_lessons: 用户课时完成记录（一对多）
    """

    __tablename__ = "lessons"

    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属课程ID",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="课时标题")
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="课时描述"
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="text",
        comment="类型: video/text/interactive/quiz/game",
    )
    duration: Mapped[int] = mapped_column(
        Integer, default=0, comment="课时时长(分钟)"
    )
    order: Mapped[int] = mapped_column(
        Integer, default=0, comment="课时顺序"
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="课时内容"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    knowledge_node_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联知识点ID（quiz 类型课时绑定）",
    )

    # 关系
    course: Mapped["Course"] = relationship("Course", back_populates="lessons")
    user_lessons: Mapped[List["UserLesson"]] = relationship(
        "UserLesson", back_populates="lesson", lazy="selectin"
    )
    knowledge_node_rel: Mapped[Optional["KnowledgeNode"]] = relationship("KnowledgeNode")

    __table_args__ = (
        Index("ix_lessons_course_order", "course_id", "order"),
    )


class UserCourse(BaseModel, Base):
    """
    用户课程关联模型（学习进度）

    记录用户与课程的关联关系，追踪用户在某门课程上的学习进度。
    同一用户同一课程仅有一条记录（通过唯一约束保证）。

    Attributes:
        user_id: 用户 ID（外键，级联删除）
        course_id: 课程 ID（外键，级联删除）
        progress: 学习进度百分比（0-100）
        completed_lessons: 已完成课时数量
        status: 学习状态（enrolled/completed）
        last_accessed_at: 最近访问时间
        course: 关联的课程对象（多对一）
    """

    __tablename__ = "user_courses"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="课程ID",
    )
    progress: Mapped[int] = mapped_column(
        Integer, default=0, comment="学习进度(0-100)"
    )
    completed_lessons: Mapped[int] = mapped_column(
        Integer, default=0, comment="已完成课时数"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="enrolled",
        comment="状态: enrolled/completed",
    )
    last_accessed_at = mapped_column(
        DateTime,
        nullable=True,
        comment="最近学习时间",
    )

    # 关系
    course: Mapped["Course"] = relationship("Course", back_populates="user_courses")

    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_user_course"),
        Index("ix_user_courses_user_status", "user_id", "status"),
    )


class UserLesson(BaseModel, Base):
    """
    用户课时完成记录模型

    记录用户对具体课时的完成情况，包括是否完成和学习用时。
    同一用户同一课时仅有一条记录（通过唯一约束保证）。

    Attributes:
        user_id: 用户 ID（外键，级联删除）
        lesson_id: 课时 ID（外键，级联删除）
        course_id: 课程 ID（外键，级联删除）
        completed: 是否已完成
        time_spent_seconds: 学习用时（秒）
        lesson: 关联的课时对象（多对一）
    """

    __tablename__ = "user_lessons"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="课时ID",
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="课程ID",
    )
    completed: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已完成"
    )
    time_spent_seconds: Mapped[int] = mapped_column(
        Integer, default=0, comment="学习用时(秒)"
    )

    # 关系
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="user_lessons")

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),
    )


class ChatMessage(BaseModel, Base):
    """
    AI 对话历史模型

    存储用户与 AI 助教的多轮对话消息，支持关联到具体课程和课时上下文。
    消息角色分为 user（用户提问）和 assistant（AI 回答）。

    Attributes:
        user_id: 用户 ID（外键，可选，游客模式可为空）
        course_id: 关联课程 ID（外键，可选）
        lesson_id: 关联课时 ID（外键，可选）
        role: 消息角色（user/assistant）
        content: 消息内容（富文本/Markdown）
        context: 上下文信息（JSON，如引用知识点、学习进度等）
    """

    __tablename__ = "chat_messages"

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="用户ID",
    )
    course_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="课程ID",
    )
    lesson_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="课时ID",
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="角色: user/assistant"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    context: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="上下文信息"
    )

    __table_args__ = (
        Index("ix_chat_messages_user_created", "user_id", "created_at"),
    )
