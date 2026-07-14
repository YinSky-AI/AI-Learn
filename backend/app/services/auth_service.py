# -*- coding: utf-8 -*-
"""
用户认证服务模块

提供用户注册、登录、Token 刷新等核心业务逻辑。
负责密码哈希管理、年龄分级计算、Token 生成与验证。

主要功能：
    - 用户注册：校验唯一性、计算年龄分级、创建用户记录、生成 JWT Token
    - 用户登录：校验凭据、更新登录时间、生成 Token
    - Token 刷新：验证 refresh_token、检查用户状态、签发新 Token
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

    分级规则：
        AGE_06_09: 年龄小于 10 岁
        AGE_10_12: 年龄 10 ~ 12 岁
        AGE_13_15: 年龄 13 ~ 15 岁
        AGE_16_18: 年龄 16 岁及以上

    Args:
        birth_date (date): 用户出生日期

    Returns:
        str: 年龄分级编码
    """
    today = date.today()
    # 精确计算周岁（考虑月份和日期）
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

    完整的用户注册流程：
        1. 校验邮箱必填与唯一性
        2. 解析/推算出生日期并计算年龄分级
        3. 创建用户记录（密码哈希存储）
        4. 生成 JWT Token 对并返回

    Args:
        db (AsyncSession): 异步数据库会话
        request (RegisterRequest): 注册请求数据

    Returns:
        TokenResponse: 包含 access_token 与 refresh_token 的响应

    Raises:
        HTTPException: 邮箱重复或参数格式错误时抛出
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

    # 检查邮箱唯一性（排除已删除用户）
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

    # 解析出生日期（优先使用 birth_date，否则根据 age 推算，最后使用默认值）
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

    # 创建用户记录
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
    await db.flush()  # 获取数据库生成的 ID

    # 生成 JWT Token 对
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800,  # access_token 有效期 30 分钟
    )


async def login_user(
    db: AsyncSession,
    request: LoginRequest,
) -> TokenResponse:
    """
    用户登录

    登录流程：
        1. 校验 identifier（邮箱或昵称）
        2. 查询用户并验证密码哈希
        3. 更新最后登录日期
        4. 生成并返回 JWT Token 对

    Args:
        db (AsyncSession): 异步数据库会话
        request (LoginRequest): 登录请求数据

    Returns:
        TokenResponse: 包含 access_token 与 refresh_token 的响应

    Raises:
        HTTPException: 凭据错误时抛出 401
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

    # 同时尝试匹配 email 或 nickname（支持两种登录方式）
    from sqlalchemy import or_
    stmt = select(User).where(
        or_(User.email == identifier, User.nickname == identifier),
        User.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # 校验用户存在性与密码正确性
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

    # 生成 JWT Token 对
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800,  # access_token 有效期 30 分钟
    )


async def refresh_token(
    db: AsyncSession,
    refresh_token_str: str,
) -> TokenResponse:
    """
    刷新 Token

    Token 刷新流程：
        1. 解码并验证 refresh_token 的有效性与类型
        2. 检查对应用户是否存在且未被删除
        3. 生成新的 access_token 与 refresh_token

    Args:
        db (AsyncSession): 异步数据库会话
        refresh_token_str (str): 客户端提交的 refresh_token

    Returns:
        TokenResponse: 新的 Token 对

    Raises:
        HTTPException: refresh_token 无效、过期或用户不存在时抛出 401
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

    # 从 payload 提取用户 ID 并查询用户状态
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
        expires_in=1800,  # access_token 有效期 30 分钟
    )
