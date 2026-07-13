# -*- coding: utf-8 -*-
"""
成就 API
处理成就列表查询、用户成就展示
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
    获取所有成就列表
    不需要登录即可查看
    """
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
    获取我的成就列表（含解锁状态）
    """
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
    检查并发放成就
    系统自动检查用户是否满足成就条件
    """
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
