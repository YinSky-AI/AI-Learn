# -*- coding: utf-8 -*-
"""
用户相关 Pydantic Schema 模块

定义用户（User）的完整请求/响应数据模型，包括：
- 用户注册和创建（UserCreate）
- 用户信息更新（UserUpdate）
- 用户信息响应（UserResponse、UserBrief）
- 用户行为档案（UserProfileResponse）
- 用户学习统计（UserStatsResponse）

Schema 遵循分层设计：
- Base: 共享字段（nickname、birth_date）
- Create: 创建时需要的全部字段
- Update: 部分更新，所有字段可选
- Response: 面向客户端的安全响应（不含密码等敏感字段）
"""

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """
    用户基础信息模型

    定义用户的共享字段，被 UserCreate 继承。
    """
    nickname: str = Field(..., min_length=1, max_length=50, description="昵称")
    birth_date: date = Field(..., description="出生日期")


class UserCreate(UserBase):
    """
    创建用户请求模型

    继承 UserBase，额外包含邮箱和密码字段。
    密码最小长度 6 字符，最大长度 128 字符。
    """
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码")


class UserUpdate(BaseModel):
    """
    更新用户信息请求模型

    所有字段均为可选，支持 PATCH 方式的部分更新。
    目前支持更新昵称和头像 URL。
    """
    nickname: Optional[str] = Field(None, min_length=1, max_length=50, description="昵称")
    avatar_url: Optional[str] = Field(None, max_length=500, description="头像 URL")


class UserResponse(BaseModel):
    """
    用户信息响应模型

    返回用户的完整信息（不含密码等敏感字段），用于个人资料页等场景。
    """
    id: UUID
    nickname: str
    email: str
    birth_date: date
    age_group: str
    avatar_url: Optional[str] = None
    total_score: int
    streak_days: int
    behavior_profile: Optional[Any] = None
    last_login_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserBrief(BaseModel):
    """
    用户简要信息模型（列表展示用）

    用于排行榜、用户列表等场景，仅包含展示所需的核心字段。
    """
    id: UUID
    nickname: str
    avatar_url: Optional[str] = None
    age_group: str
    total_score: int
    streak_days: int

    model_config = {"from_attributes": True}


class UserProfileResponse(BaseModel):
    """
    用户行为档案响应模型

    返回用户的学习档案信息，重点展示 AI 行为模型和学习成就数据。
    """
    id: UUID
    nickname: str
    age_group: str
    total_score: int
    streak_days: int
    behavior_profile: Optional[Any] = None

    model_config = {"from_attributes": True}


class UserStatsResponse(BaseModel):
    """
    用户学习统计响应模型

    返回用户的学习统计数据 dashboard，包含积分、连续学习、今日/本周学习时长、
    课程进度等核心指标。
    """
    total_score: int  # 总经验值
    streak_days: int  # 连续学习天数
    today_study_minutes: int  # 今日学习分钟数
    week_study_hours: float  # 本周学习小时数
    total_completed_lessons: int  # 已完成课时数
    in_progress_courses: int  # 进行中课程数
    completed_courses: int  # 已完成课程数
    overall_progress: int  # 总体进度百分比

    model_config = {"from_attributes": True}
