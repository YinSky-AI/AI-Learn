# -*- coding: utf-8 -*-
"""
认证相关 Schema
定义登录、注册、Token 等数据结构
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求"""
    nickname: str = Field(..., min_length=1, max_length=50, description="昵称")
    email: Optional[str] = Field(None, description="邮箱（可选，未提供时使用 username）")
    username: Optional[str] = Field(None, description="用户名（可选，未提供时使用 email）")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    birth_date: Optional[str] = Field(None, description="出生日期 (YYYY-MM-DD)，可选")
    age: Optional[int] = Field(None, description="年龄，用于推算出生日期")

    def get_email(self) -> str:
        """获取有效的邮箱/用户名"""
        return self.email or self.username or ""


class LoginRequest(BaseModel):
    """登录请求"""
    email: Optional[str] = Field(None, description="邮箱")
    username: Optional[str] = Field(None, description="用户名")
    password: str = Field(..., min_length=1, description="密码")

    def get_identifier(self) -> str:
        """获取登录标识（邮箱或用户名）"""
        return self.email or self.username or ""


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求"""
    refresh_token: str = Field(..., description="刷新令牌")


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")


class TokenPayload(BaseModel):
    """Token 载荷"""
    sub: str = Field(..., description="用户 ID")
    type: str = Field(..., description="令牌类型")
    exp: int = Field(..., description="过期时间")
    iat: int = Field(..., description="签发时间")
