# -*- coding: utf-8 -*-
"""
用户管理 API 模块

提供当前登录用户的信息查询、资料更新、行为档案与学习统计等接口。
所有接口均需登录认证，通过依赖注入获取当前用户身份。

主要功能：
    - 获取/更新当前用户信息
    - 获取用户行为档案（行为模型、学习偏好等）
    - 获取用户学习统计数据（学习时长、完成课时、课程进度等）
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id, get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.user import UserResponse, UserUpdate, UserProfileResponse, UserStatsResponse
from app.services import user_service

router = APIRouter()


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_my_info(
    user: User = Depends(get_current_user),
):
    """
    获取当前登录用户信息

    Args:
        user (User): 通过依赖注入获取的当前登录用户对象

    Returns:
        ApiResponse[UserResponse]: 用户基本信息（昵称、邮箱、年龄分级等）
    """
    # 直接将 ORM 用户对象转换为响应模型返回
    return success_response(
        data=UserResponse.model_validate(user),
        message="获取用户信息成功",
    )


@router.put("/me", response_model=ApiResponse[UserResponse])
async def update_my_info(
    update_data: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新当前登录用户信息

    支持部分字段更新，仅更新请求体中提供的非 None 字段。

    Args:
        update_data (UserUpdate): 用户更新请求体（昵称、头像、年龄等可选字段）
        user (User): 当前登录用户对象
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[UserResponse]: 更新后的用户信息

    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    # 调用用户服务执行字段级更新
    updated_user = await user_service.update_user(db, user.id, update_data)
    return success_response(
        data=UserResponse.model_validate(updated_user),
        message="用户信息更新成功",
    )


@router.get("/me/profile", response_model=ApiResponse[UserProfileResponse])
async def get_my_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户行为档案

    返回用户的行为模型数据，包括学习偏好、能力评估等。

    Args:
        user_id (uuid.UUID): 当前登录用户 ID（由依赖注入解析）
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[UserProfileResponse]: 用户行为档案详情
    """
    # 从用户服务获取行为档案（含行为模型 JSON 数据）
    profile = await user_service.get_user_profile(db, user_id)
    return success_response(
        data=profile,
        message="获取行为档案成功",
    )


@router.get("/me/stats", response_model=ApiResponse[UserStatsResponse])
async def get_my_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户学习统计

    综合统计用户的学习时长（今日/本周）、已完成课时数、进行中/已完成课程数及总体进度。

    Args:
        user_id (uuid.UUID): 当前登录用户 ID（由依赖注入解析）
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[UserStatsResponse]: 学习统计数据
    """
    # 调用用户服务聚合多表学习统计数据
    stats = await user_service.get_user_stats(db, user_id)
    return success_response(data=stats, message="获取学习统计成功")
