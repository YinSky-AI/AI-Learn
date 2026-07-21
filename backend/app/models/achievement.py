# -*- coding: utf-8 -*-
"""
成就相关模型定义模块

定义成就（Achievement）和用户成就关联（UserAchievement）数据模型，
支撑平台的游戏化学习激励体系。

成就系统工作流程：
1. 管理员预定义 Achievement 记录（编码、名称、达成条件、徽章图标）
2. 系统检测用户行为是否满足 Achievement.criteria 中的条件
3. 条件满足时创建 UserAchievement 记录，用户获得成就徽章

成就类型示例：首次学习（FIRST_LEARN）、连续学习 7 天（STREAK_7）等。
"""

from sqlalchemy import Column, String, Text, DateTime, Index, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import BaseModel
from app.models import Base


class Achievement(BaseModel, Base):
    """
    成就模型

    定义系统中可获得的成就徽章模板，包含达成条件和展示信息。
    成就记录由管理员预置，用户通过满足条件获得对应的 UserAchievement 记录。

    Attributes:
        code: 成就唯一编码（如 FIRST_LEARN、STREAK_7）
        name: 成就显示名称（如 "初次学习"）
        description: 达成条件描述（面向用户的说明文本）
        icon_url: 徽章图标 URL
        criteria: 达成条件配置（JSONB，如 {"min_streak": 7}）
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

    记录用户达成某个成就的具体时间，是用户成就墙的数据来源。
    同一用户同一成就仅有一条记录（通常由唯一约束或业务逻辑保证）。

    Attributes:
        user_id: 用户 ID（外键，级联删除）
        achievement_id: 成就 ID（外键，级联删除）
        achieved_at: 达成时间（由业务逻辑在条件满足时设置）
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
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement_user_achievement"),
    )

    def __repr__(self) -> str:
        return f"<UserAchievement(id={self.id}, user_id={self.user_id})>"
