# -*- coding: utf-8 -*-
"""
认证服务
处理用户注册、登录、Token 刷新
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)


def _calculate_age_group(birth_date: date) -> str:
    """
    根据出生日期计算年龄分级
    AGE_06_09 / AGE_10_12 / AGE_13_15 / AGE_16_18
    """
    today = date.today()
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    if age < 10:
        return "AGE_06_09"
    elif age < 13:
        return "AGE_10_12"
    elif age < 16:
        return "AGE_13_15"
    else:
        return "AGE_16_18"


async def register_user(
    db: AsyncSession,
    request: RegisterRequest,
) -> TokenResponse:
    """
    注册新用户
    1. 检查邮箱/用户名是否已存在
    2. 计算年龄分级
    3. 创建用户
    4. 生成 Token
    """
    email = request.get_email()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VAL_002",
                "message": "请提供邮箱或用户名",
            },
        )

    # 检查邮箱唯一性
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "BIZ_001",
                "message": "该邮箱已被注册",
            },
        )

    # 解析出生日期（优先使用 birth_date，否则根据 age 推算）
    if request.birth_date:
        try:
            birth_date = date.fromisoformat(request.birth_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "VAL_001",
                    "message": "出生日期格式无效，请使用 YYYY-MM-DD 格式",
                },
            )
    elif request.age is not None:
        birth_year = date.today().year - request.age
        birth_date = date(birth_year, 1, 1)
    else:
        birth_date = date(2015, 1, 1)  # 默认年龄约 10 岁

    # 计算年龄分级
    age_group = _calculate_age_group(birth_date)

    # 创建用户
    user = User(
        id=uuid.uuid4(),
        nickname=request.nickname,
        email=email,
        password_hash=hash_password(request.password),
        birth_date=birth_date,
        age_group=age_group,
        last_login_date=date.today(),
    )
    db.add(user)
    await db.flush()  # 获取 ID

    # 生成 Token
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800,  # 30分钟
    )


async def login_user(
    db: AsyncSession,
    request: LoginRequest,
) -> TokenResponse:
    """
    用户登录
    1. 验证邮箱/用户名和密码
    2. 更新登录日期
    3. 生成 Token
    """
    identifier = request.get_identifier()
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VAL_003",
                "message": "请提供邮箱或用户名",
            },
        )

    # 同时尝试匹配 email 或 nickname
    from sqlalchemy import or_
    stmt = select(User).where(
        or_(User.email == identifier, User.nickname == identifier),
        User.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_001",
                "message": "用户名或密码错误",
            },
        )

    # 更新最后登录日期
    user.last_login_date = date.today()
    db.add(user)
    await db.flush()

    # 生成 Token
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800,
    )


async def refresh_token(
    db: AsyncSession,
    refresh_token_str: str,
) -> TokenResponse:
    """
    刷新 Token
    1. 验证 refresh token
    2. 检查用户是否存在
    3. 生成新的 access token
    """
    try:
        payload = decode_token(refresh_token_str)
        if payload.get("type") != "refresh":
            raise ValueError("Token 类型错误")
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_002",
                "message": "刷新令牌无效或已过期",
            },
        )

    user_id = uuid.UUID(payload["sub"])
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

    # 生成新的 Token 对
    access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=1800,
    )
