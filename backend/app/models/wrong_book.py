"""错题本数据模型。"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import BaseModel
from app.models import Base


class WrongQuestion(BaseModel, Base):
    """用户错题的唯一聚合记录；同一用户同一道题只保存一行。"""

    __tablename__ = "wrong_questions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    subject = Column(String(50), nullable=False)
    wrong_count = Column(Integer, nullable=False, default=1, server_default="1")
    first_wrong_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_wrong_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_wrong_answer = Column(Text, nullable=False, default="", server_default="")
    is_mastered = Column(Boolean, nullable=False, default=False, server_default="false")
    mastered_at = Column(DateTime(timezone=True), nullable=True)
    review_count = Column(Integer, nullable=False, default=0, server_default="0")
    scheduler_version = Column(String(20), nullable=False, default="v1", server_default="v1")
    difficulty_factor = Column(Integer, nullable=False, default=100, server_default="100")
    next_review_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    user_note = Column(Text, nullable=False, default="", server_default="")

    question = relationship("Question", lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_wrong_question_user_question"),
        Index("idx_wrong_question_user_subject", "user_id", "subject"),
        Index("idx_wrong_question_user_review", "user_id", "is_mastered", "last_wrong_at"),
        Index("idx_wrong_question_due", "user_id", "is_mastered", "next_review_at"),
    )


class WrongQuestionEvent(BaseModel, Base):
    """已处理的正式答错事件，用 Answer.id 保证重试不重复累计。"""

    __tablename__ = "wrong_question_events"

    answer_id = Column(UUID(as_uuid=True), ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (Index("idx_wrong_question_event_user_question", "user_id", "question_id"),)
