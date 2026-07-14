# -*- coding: utf-8 -*-
"""
学习相关模型定义模块

定义学习会话（LearningSession）和答题记录（Answer）数据模型，
支撑平台的自适应学习核心流程。

数据流：
1. 用户开始知识点学习 -> 创建 LearningSession（状态 in_progress）
2. 用户逐题作答 -> 创建 Answer 记录
3. 学习结束 -> 更新 LearningSession 状态为 completed 并统计正确率

LearningSession 是答题记录的聚合根，Answer 是会话内的子记录。
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import BaseModel
from app.models import Base


class LearningSession(BaseModel, Base):
    """
    学习会话模型

    记录用户针对某一知识点的一次完整学习过程，是会话内所有答题记录的聚合根。
    会话状态流转：in_progress -> completed / abandoned

    Attributes:
        user_id: 用户 ID（外键，级联删除）
        knowledge_node_id: 学习的知识点 ID（外键，级联删除）
        difficulty_level: 本次学习选择的难度等级
        status: 会话状态（in_progress / completed / abandoned）
        started_at: 会话开始时间（数据库默认值 NOW()）
        completed_at: 会话完成时间，未结束时为 None
        correct_count: 答对题数
        total_questions: 总题数
        answers: 关联的答题记录列表（一对多）
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

    记录用户在学习会话中对每道题目的作答详情，包括答案、正确性和用时。
    答题记录用于统计学习效果、更新用户行为模型和生成学习报告。

    Attributes:
        session_id: 所属学习会话 ID（外键，级联删除）
        question_id: 回答的题目 ID（外键，级联删除）
        user_answer: 用户提交的答案文本
        is_correct: 是否正确
        time_spent_seconds: 答题用时（秒）
        answered_at: 答题时间（数据库默认值 NOW()）
        session_rel: 关联的学习会话对象（多对一）
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
