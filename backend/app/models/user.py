# -*- coding: utf-8 -*-
"""
用户模型定义模块

定义 User 数据模型，存储用户的基本信息、登录凭证、积分统计和行为模型。
用户是平台的核心实体，与课程学习、答题记录、成就等模块均有关联。

字段设计：
- 基本信息：昵称、邮箱、密码哈希、出生日期、年龄分级、头像
- 积分统计：总积分、连续学习天数
- 行为模型：JSONB 存储的能力估计、行为模式、偏好冲突、置信度
- 管理关联：与若依管理后台的账号同步
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, Float, Integer, String, Index, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import SoftDeleteModel
from app.models import Base


class User(SoftDeleteModel, Base):
    """
    用户模型

    存储平台注册用户的基本信息、登录凭证、积分统计和 AI 行为模型。
    继承 SoftDeleteModel 支持软删除，继承 Base 获得声明式映射能力。

    Attributes:
        nickname: 用户昵称，最大 50 字符
        email: 用户邮箱，唯一标识，用于登录
        password_hash: bcrypt 哈希后的密码，不存储明文
        birth_date: 出生日期，用于计算年龄和分级
        age_group: 年龄分级编码（如 AGE_06_09）
        avatar_url: 头像图片 URL
        total_score: 用户总积分，反映学习积累
        streak_days: 连续学习天数，用于激励体系
        behavior_profile: JSONB 行为模型，支持 AI 自适应学习
        last_login_date: 上次登录日期
        admin_user_id: 管理后台关联 ID（预留字段）
        is_admin: 是否为管理员
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
    current_correct_streak = Column(Integer, default=0, server_default="0", nullable=False, comment="当前连续答对题数")
    max_correct_streak = Column(Integer, default=0, server_default="0", nullable=False, comment="最高连续答对题数")
    total_answered = Column(Integer, default=0, server_default="0", nullable=False, comment="累计作答数")
    correct_answered = Column(Integer, default=0, server_default="0", nullable=False, comment="累计答对数")
    last_active_date = Column(Date, nullable=True, comment="最后学习日期")
    study_days_count = Column(Integer, default=0, server_default="0", nullable=False, comment="累计学习天数")

    # 行为模型 (JSONB 灵活配置)
    behavior_profile = Column(JSONB, nullable=True, comment="用户行为模型（能力估计、行为模式、偏好冲突、置信度）")

    # 登录信息
    last_login_date = Column(Date, nullable=True, comment="上次登录日期")

    # 管理后台关联（预留字段）
    admin_user_id = Column(Integer, nullable=True, unique=True,
                           comment="管理后台用户 ID，用于关联外部管理系统")
    is_admin = Column(Boolean, default=False, server_default=text("false"),
                     comment="是否为管理员")

    # 索引
    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_age_group", "age_group"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, nickname={self.nickname}, email={self.email})>"
