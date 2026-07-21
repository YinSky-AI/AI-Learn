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
    user_note = Column(Text, nullable=False, default="", server_default="")

    question = relationship("Question", lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_wrong_question_user_question"),
        Index("idx_wrong_question_user_subject", "user_id", "subject"),
        Index("idx_wrong_question_user_review", "user_id", "is_mastered", "last_wrong_at"),
    )
