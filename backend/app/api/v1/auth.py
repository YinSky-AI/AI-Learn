# -*- coding: utf-8 -*-
"""
认证 API
处理用户注册、登录、Token 刷新
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
    用户注册
    创建新用户并返回 Token 对
    """
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
    用户登录
    验证邮箱密码并返回 Token 对
    """
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
    刷新 Token
    使用 refresh token 换取新的 Token 对
    """
    token = await auth_service.refresh_token(db, request.refresh_token)
    return ApiResponse(
        code="SUCCESS",
        message="Token 刷新成功",
        data=token,
    )
