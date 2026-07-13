# -*- coding: utf-8 -*-
"""
用户模型
定义 User 表结构和相关枚举
"""

from datetime import date, datetime

from sqlalchemy import Column, Date, Float, Integer, String, Index, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import SoftDeleteModel
from app.models import Base


class User(SoftDeleteModel, Base):
    """
    用户模型
    存储用户基本信息、登录凭证、积分和行为模型
    """

    __tablename__ = "users"

    # 基本信息
    nickname = Column(String(50), nullable=False, comment="昵称")
    email = Column(String(255), unique=True, nullable=False, comment="邮箱（登录凭证）")
    password_hash = Column(String(255), nullable=False, comment="bcrypt 密码哈希")
    birth_date = Column(Date, nullable=False, comment="出生日期，用于计算年龄分级")
    age_group = Column(String(10), nullable=False, comment="当前年龄分级编码")
    avatar_url = Column(String(500), nullable=True, comment="头像 URL")

    # 积分和统计
    total_score = Column(Integer, default=0, server_default="0", comment="总积分")
    streak_days = Column(Integer, default=0, server_default="0", comment="连续学习天数")

    # 行为模型 (JSONB 灵活配置)
    behavior_profile = Column(JSONB, nullable=True, comment="用户行为模型（能力估计、行为模式、偏好冲突、置信度）")

    # 登录信息
    last_login_date = Column(Date, nullable=True, comment="上次登录日期")

    # 索引
    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_age_group", "age_group"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, nickname={self.nickname}, email={self.email})>"
