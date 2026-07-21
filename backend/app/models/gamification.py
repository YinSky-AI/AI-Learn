# -*- coding: utf-8 -*-
"""答题奖励事件模型：以 answer_id 作为幂等键。"""

from sqlalchemy import Column, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import BaseModel
from app.models import Base


class GamificationEvent(BaseModel, Base):
    __tablename__ = "gamification_events"

    answer_id = Column(UUID(as_uuid=True), ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    points_earned = Column(Integer, nullable=False, server_default="0")
    base_points = Column(Integer, nullable=False, server_default="0")
    streak_bonus = Column(Integer, nullable=False, server_default="0")
    level = Column(Integer, nullable=False, server_default="1")
    correct_streak = Column(Integer, nullable=False, server_default="0")
    new_achievements = Column(JSONB, nullable=False, server_default="[]")

    __table_args__ = (Index("idx_gamification_event_user", "user_id"),)
