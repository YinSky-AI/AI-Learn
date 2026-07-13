# -*- coding: utf-8 -*-
"""
用户相关 Pydantic Schema
定义用户信息的请求/响应数据结构
"""

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """用户基础信息"""
    nickname: str = Field(..., min_length=1, max_length=50, description="昵称")
    birth_date: date = Field(..., description="出生日期")


class UserCreate(UserBase):
    """创建用户请求"""
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码")


class UserUpdate(BaseModel):
    """更新用户信息请求（所有字段可选）"""
    nickname: Optional[str] = Field(None, min_length=1, max_length=50, description="昵称")
    avatar_url: Optional[str] = Field(None, max_length=500, description="头像 URL")


class UserResponse(BaseModel):
    """用户信息响应"""
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
    """用户简要信息（列表展示用）"""
    id: UUID
    nickname: str
    avatar_url: Optional[str] = None
    age_group: str
    total_score: int
    streak_days: int

    model_config = {"from_attributes": True}


class UserProfileResponse(BaseModel):
    """用户行为档案响应"""
    id: UUID
    nickname: str
    age_group: str
    total_score: int
    streak_days: int
    behavior_profile: Optional[Any] = None

    model_config = {"from_attributes": True}


class UserStatsResponse(BaseModel):
    """用户学习统计响应"""
    total_score: int  # 总经验值
    streak_days: int  # 连续学习天数
    today_study_minutes: int  # 今日学习分钟数
    week_study_hours: float  # 本周学习小时数
    total_completed_lessons: int  # 已完成课时数
    in_progress_courses: int  # 进行中课程数
    completed_courses: int  # 已完成课程数
    overall_progress: int  # 总体进度百分比

    model_config = {"from_attributes": True}
