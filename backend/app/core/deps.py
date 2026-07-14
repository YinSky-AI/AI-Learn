# -*- coding: utf-8 -*-
"""
依赖注入模块

提供 FastAPI 路由中常用的依赖项函数，用于：
- 认证与授权：从请求头提取 JWT Token 并验证用户身份
- 数据库会话：为每个请求提供独立的数据库事务会话
- 分页参数：统一处理列表接口的分页请求参数

依赖项可在路由函数中通过 FastAPI 的 Depends 使用，实现关注点分离和代码复用。
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
    获取当前用户 ID（强制认证）

    从 HTTP Authorization 请求头中提取 Bearer Token，解码并验证 JWT 令牌。
    仅接受 access 类型的令牌，验证通过后返回用户 UUID。

    Args:
        credentials: HTTP Bearer 认证凭据，由 FastAPI Security 自动解析

    Returns:
        uuid.UUID: 当前登录用户的唯一标识符

    Raises:
        HTTPException: 401 未授权，原因包括：未提供令牌、令牌无效、令牌类型错误、令牌已过期
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
    获取当前用户完整对象（强制认证）

    基于 get_current_user_id 获取的用户 ID，从数据库查询对应的用户记录。
    自动过滤已软删除的用户，确保返回活跃用户信息。

    Args:
        user_id: 当前用户 ID，由 get_current_user_id 依赖注入
        db: 异步数据库会话，由 get_db 依赖注入

    Returns:
        User: 当前登录用户的完整 ORM 对象

    Raises:
        HTTPException: 401 未授权，当用户不存在或已被软删除时抛出
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

    统一处理列表查询接口的分页参数，将页码和每页数量转换为 offset 和 limit，
    便于直接用于 SQLAlchemy 查询切片。

    Args:
        page: 当前页码，最小值为 1，默认 1
        page_size: 每页记录数，范围 1-100，默认 20

    Returns:
        dict: 包含 page、page_size、offset、limit 的字典
              offset = (page - 1) * page_size
              limit = page_size
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
    获取当前用户 ID（可选认证）

    与 get_current_user_id 类似，但不强制要求认证。
    未提供 Token 或 Token 无效时返回 None，而不是抛出 401 异常。
    适用于同时支持匿名访问和登录访问的接口（如公开课程列表、游客模式等）。

    Args:
        credentials: HTTP Bearer 认证凭据，由 FastAPI Security 自动解析

    Returns:
        Optional[uuid.UUID]: 当前登录用户的唯一标识符，未登录或令牌无效时返回 None
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
