# -*- coding: utf-8 -*-
"""
依赖注入模块
提供公共的 FastAPI 依赖项
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

# Bearer Token 安全方案
security = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> uuid.UUID:
    """
    从请求头中提取并验证 JWT Token，返回当前用户 ID
    用于需要认证的接口
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_001",
                "message": "未提供认证令牌，请先登录",
            },
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Token 类型错误")
        user_id = uuid.UUID(payload["sub"])
        return user_id
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_002",
                "message": f"认证令牌无效或已过期: {str(e)}",
            },
        )


async def get_current_user(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从数据库获取当前用户完整对象
    包含软删除检查
    """
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_003",
                "message": "用户不存在或已被删除",
            },
        )
    return user


def get_pagination_params(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> dict:
    """
    分页参数依赖
    返回 offset 和 limit
    """
    return {
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
        "limit": page_size,
    }


def get_current_user_id_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[uuid.UUID]:
    """
    可选认证：有 Token 则返回用户 ID，无 Token 返回 None
    用于可选登录的接口
    """
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        return None
