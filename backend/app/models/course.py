# -*- coding: utf-8 -*-
"""
课程与课时模型
包含 Course、Lesson、用户学习记录、AI对话历史
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.models import Base


class Course(BaseModel, Base):
    """课程模型"""

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
    """课时模型"""

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

    # 关系
    course: Mapped["Course"] = relationship("Course", back_populates="lessons")
    user_lessons: Mapped[List["UserLesson"]] = relationship(
        "UserLesson", back_populates="lesson", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_lessons_course_order", "course_id", "order"),
    )


class UserCourse(BaseModel, Base):
    """用户课程关联（学习进度）"""

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
    """用户课时完成记录"""

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
    """AI 对话历史"""

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
