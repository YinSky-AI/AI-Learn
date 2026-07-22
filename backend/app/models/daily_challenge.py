"""Persistence for server-authoritative daily challenges."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import BaseModel
from app.models import Base


class DailyChallenge(BaseModel, Base):
    __tablename__ = "daily_challenges"
    challenge_date = Column(Date, nullable=False, unique=True, index=True)
    subject = Column(String(50), nullable=False, default="综合")
    question_count = Column(Integer, nullable=False, default=5)
    time_limit_seconds = Column(Integer, nullable=False, default=300)
    description = Column(String(255), nullable=False, default="今日挑战：在限定时间内完成题目")


class DailyChallengeQuestion(BaseModel, Base):
    __tablename__ = "daily_challenge_questions"
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("daily_challenges.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("challenge_id", "question_id", name="uq_daily_challenge_question"), UniqueConstraint("challenge_id", "position", name="uq_daily_challenge_position"))


class DailyChallengeAttempt(BaseModel, Base):
    __tablename__ = "daily_challenge_attempts"
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("daily_challenges.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)
    total_count = Column(Integer, nullable=False, default=0)
    time_spent_seconds = Column(Integer, nullable=False, default=0)
    completed = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("challenge_id", "user_id", name="uq_daily_challenge_user_attempt"), Index("idx_daily_challenge_attempt_score", "challenge_id", "score"))


class DailyChallengeAnswer(BaseModel, Base):
    __tablename__ = "daily_challenge_answers"
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("daily_challenge_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    selected_answer = Column(String(500), nullable=False)
    event_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    is_correct = Column(Boolean, nullable=False)
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_daily_challenge_answer"),)
