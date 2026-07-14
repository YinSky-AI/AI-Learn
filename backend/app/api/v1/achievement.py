# -*- coding: utf-8 -*-
"""
成就系统 API 模块

提供成就相关的查询与检查接口，包括全部成就列表、我的成就、成就检查与发放。
成就列表接口无需认证，个人成就与检查接口需登录。

主要功能：
    - 获取系统中所有成就定义
    - 获取当前用户的成就解锁状态
    - 触发成就检查，自动发放满足条件的成就
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import ApiResponse, success_response
from app.services import achievement_service

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_all_achievements(
    db: AsyncSession = Depends(get_db),
):
    """
    获取所有成就列表接口

    公开接口，无需登录。返回系统中定义的所有成就基本信息。

    Args:
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 成就定义列表（含编码、名称、描述、图标）
    """
    # 查询所有成就定义
    achievements = await achievement_service.get_all_achievements(db)
    return success_response(
        data=[
            {
                "id": str(ach.id),
                "code": ach.code,
                "name": ach.name,
                "description": ach.description,
                "icon_url": ach.icon_url,
            }
            for ach in achievements
        ],
        message="获取成就列表成功",
    )


@router.get("/me", response_model=ApiResponse)
async def get_my_achievements(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    获取我的成就列表接口

    返回当前用户的所有成就及其解锁状态。

    Args:
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 我的成就列表（含是否已解锁标记）
    """
    # 查询用户成就解锁状态
    achievements = await achievement_service.get_user_achievements(db, user_id)
    return success_response(
        data=achievements,
        message="获取我的成就成功",
    )


@router.post("/check", response_model=ApiResponse)
async def check_achievements(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    检查并发放成就接口

    系统自动检查当前用户是否满足各项成就条件，满足则创建 UserAchievement 记录并返回新解锁成就。

    Args:
        user_id (uuid.UUID): 当前登录用户 ID
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 新解锁成就数量与列表（若有）
    """
    # 执行成就检查与自动发放
    newly_awarded = await achievement_service.check_and_award_achievements(db, user_id)
    if newly_awarded:
        return success_response(
            data={
                "newly_awarded_count": len(newly_awarded),
                "achievements": [
                    {"id": str(ua.achievement_id), "achieved_at": str(ua.achieved_at)}
                    for ua in newly_awarded
                ],
            },
            message=f"恭喜！新解锁了 {len(newly_awarded)} 个成就",
        )
    return success_response(
        data={"newly_awarded_count": 0},
        message="暂无新成就解锁",
    )
