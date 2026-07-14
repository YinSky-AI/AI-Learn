# -*- coding: utf-8 -*-
"""
用户认证 API 模块

提供用户注册、登录、Token 刷新等认证相关接口。
所有接口均无需前置认证，返回统一的 ApiResponse[TokenResponse] 格式。

主要功能：
    - 用户注册：校验邮箱唯一性，生成用户记录并下发 Token
    - 用户登录：校验邮箱/昵称与密码，更新登录时间并下发 Token
    - Token 刷新：验证 refresh_token 有效性，返回新的 Token 对
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.common import ApiResponse
from app.services import auth_service

router = APIRouter()


@router.post("/register", response_model=ApiResponse[TokenResponse])
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册接口

    创建新用户账号，校验邮箱唯一性，自动生成年龄分级，并返回 JWT Token 对。

    Args:
        request (RegisterRequest): 注册请求体，包含昵称、邮箱、密码、出生日期等
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[TokenResponse]: 注册成功返回 access_token / refresh_token

    Raises:
        HTTPException: 邮箱已注册或参数校验失败时抛出 400 错误
    """
    # 调用认证服务完成用户创建与 Token 生成
    token = await auth_service.register_user(db, request)
    return ApiResponse(
        code="SUCCESS",
        message="注册成功",
        data=token,
    )


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录接口

    验证用户提供的邮箱/昵称与密码，校验通过后更新最后登录时间并返回 Token 对。

    Args:
        request (LoginRequest): 登录请求体，包含 identifier（邮箱或昵称）和密码
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[TokenResponse]: 登录成功返回 access_token / refresh_token

    Raises:
        HTTPException: 用户名或密码错误时抛出 401 错误
    """
    # 调用认证服务完成登录校验与 Token 生成
    token = await auth_service.login_user(db, request)
    return ApiResponse(
        code="SUCCESS",
        message="登录成功",
        data=token,
    )


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Token 刷新接口

    使用有效的 refresh_token 换取新的 access_token 和 refresh_token。

    Args:
        request (RefreshTokenRequest): 刷新请求体，包含 refresh_token
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse[TokenResponse]: 刷新成功返回新的 Token 对

    Raises:
        HTTPException: refresh_token 无效、过期或用户不存在时抛出 401 错误
    """
    # 调用认证服务验证 refresh_token 并生成新的 Token 对
    token = await auth_service.refresh_token(db, request.refresh_token)
    return ApiResponse(
        code="SUCCESS",
        message="Token 刷新成功",
        data=token,
    )
