# -*- coding: utf-8 -*-
"""
成就相关模型
包含 Achievement 和 UserAchievement
"""

from sqlalchemy import Column, String, Text, DateTime, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import BaseModel
from app.models import Base


class Achievement(BaseModel, Base):
    """
    成就模型
    定义系统中的所有成就
    """

    __tablename__ = "achievements"

    code = Column(String(50), unique=True, nullable=False, comment="成就编码 (FIRST_LEARN / STREAK_7 / ...)")
    name = Column(String(100), nullable=False, comment="成就名称")
    description = Column(Text, nullable=True, comment="达成条件描述")
    icon_url = Column(String(500), nullable=True, comment="徽章图标")
    criteria = Column(JSONB, nullable=False, comment="达成条件配置")

    def __repr__(self) -> str:
        return f"<Achievement(id={self.id}, code={self.code}, name={self.name})>"


class UserAchievement(BaseModel, Base):
    """
    用户成就关联模型
    记录用户达成某个成就的时间
    """

    __tablename__ = "user_achievements"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户 ID",
    )
    achievement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
        comment="成就 ID",
    )
    achieved_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="达成时间",
    )

    # 索引
    __table_args__ = (
        Index("idx_user_achievement_user", "user_id"),
        Index("idx_user_achievement_achieved", "achievement_id"),
    )

    def __repr__(self) -> str:
        return f"<UserAchievement(id={self.id}, user_id={self.user_id})>"
