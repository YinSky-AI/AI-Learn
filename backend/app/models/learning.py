# -*- coding: utf-8 -*-
"""
学习相关模型
包含 LearningSession 和 Answer
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import BaseModel
from app.models import Base


class LearningSession(BaseModel, Base):
    """
    学习会话模型
    记录一次学习过程的整体信息
    """

    __tablename__ = "learning_sessions"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户 ID",
    )
    knowledge_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="知识点 ID",
    )
    difficulty_level = Column(String(10), nullable=False, comment="学习时的难度")
    status = Column(
        String(20),
        default="in_progress",
        server_default="in_progress",
        comment="状态: in_progress / completed / abandoned",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="开始时间",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成时间",
    )
    correct_count = Column(Integer, default=0, server_default="0", comment="正确数")
    total_questions = Column(Integer, default=0, server_default="0", comment="总题数")

    # 关联
    answers = relationship("Answer", back_populates="session_rel")

    # 索引
    __table_args__ = (
        Index("idx_session_user", "user_id"),
        Index("idx_session_node", "knowledge_node_id"),
    )

    def __repr__(self) -> str:
        return f"<LearningSession(id={self.id}, status={self.status})>"


class Answer(BaseModel, Base):
    """
    答题记录模型
    记录用户对每道题的回答
    """

    __tablename__ = "answers"

    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("learning_sessions.id", ondelete="CASCADE"),
        nullable=False,
        comment="会话 ID",
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        comment="题目 ID",
    )
    user_answer = Column(String(500), nullable=False, comment="用户答案")
    is_correct = Column(Boolean, nullable=False, comment="是否正确")
    time_spent_seconds = Column(Integer, nullable=False, comment="用时（秒）")
    answered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="答题时间",
    )

    # 关联
    session_rel = relationship("LearningSession", back_populates="answers")

    # 索引
    __table_args__ = (
        Index("idx_answer_session", "session_id"),
        Index("idx_answer_question", "question_id"),
    )

    def __repr__(self) -> str:
        return f"<Answer(id={self.id}, correct={self.is_correct})>"
