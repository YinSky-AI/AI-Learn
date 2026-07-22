"""当前用户的学习行为画像与报告接口。"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.schemas.common import ApiResponse, success_response
from app.services.behavior_service import BehaviorService

router = APIRouter()


@router.get("/report", response_model=ApiResponse)
async def get_behavior_report(
    days: int = Query(default=30, ge=1, le=90, description="报告时间范围（天）"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取当前登录用户的报告；结果不会包含其他用户的数据。"""
    report = await BehaviorService(db).get_learning_report(user_id, days=days)
    return success_response(data=report, message="获取学习报告成功")


@router.get("/knowledge", response_model=ApiResponse)
async def get_knowledge_mastery(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户按知识点聚合的掌握度数据。"""
    report = await BehaviorService(db).get_learning_report(user_id, days=30)
    return success_response(data=report["knowledge_heatmap"], message="获取知识点掌握度成功")
