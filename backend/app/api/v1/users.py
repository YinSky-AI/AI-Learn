# -*- coding: utf-8 -*-
"""
用户管理 API
处理用户信息查询、更新、行为档案
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
    """获取当前用户信息"""
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
    """更新当前用户信息"""
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
    """获取当前用户行为档案"""
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
    """获取当前用户学习统计"""
    stats = await user_service.get_user_stats(db, user_id)
    return success_response(data=stats, message="获取学习统计成功")
