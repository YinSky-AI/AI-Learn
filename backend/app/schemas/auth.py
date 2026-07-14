# -*- coding: utf-8 -*-
"""
认证相关 Pydantic Schema 模块

定义用户认证流程中涉及的请求和响应数据模型，包括：
- 用户注册：RegisterRequest
- 用户登录：LoginRequest
- Token 刷新：RefreshTokenRequest
- Token 响应：TokenResponse
- Token 载荷：TokenPayload

所有请求 Schema 均包含字段校验规则（如密码最小长度、邮箱格式等），
确保进入业务逻辑前的数据合法性和安全性。
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """
    用户注册请求模型

    接收用户注册所需的全部信息，支持邮箱或用户名作为登录标识。
    如果未提供出生日期但提供了年龄，后端可推算出生日期。
    """
    nickname: str = Field(..., min_length=1, max_length=50, description="昵称")
    email: Optional[str] = Field(None, description="邮箱（可选，未提供时使用 username）")
    username: Optional[str] = Field(None, description="用户名（可选，未提供时使用 email）")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    birth_date: Optional[str] = Field(None, description="出生日期 (YYYY-MM-DD)，可选")
    age: Optional[int] = Field(None, description="年龄，用于推算出生日期")

    def get_email(self) -> str:
        """
        获取有效的邮箱/用户名

        优先返回 email，其次 username，兜底返回空字符串。
        用于注册时确定用户的登录标识。

        Returns:
            str: 有效的邮箱或用户名字符串
        """
        return self.email or self.username or ""


class LoginRequest(BaseModel):
    """
    用户登录请求模型

    接收用户登录凭证，支持邮箱或用户名作为登录标识。
    密码最小长度为 1（实际校验由后端根据注册规则补充）。
    """
    email: Optional[str] = Field(None, description="邮箱")
    username: Optional[str] = Field(None, description="用户名")
    password: str = Field(..., min_length=1, description="密码")

    def get_identifier(self) -> str:
        """
        获取登录标识（邮箱或用户名）

        优先返回 email，其次 username，兜底返回空字符串。
        后端使用该标识查询用户并验证密码。

        Returns:
            str: 有效的邮箱或用户名字符串
        """
        return self.email or self.username or ""


class RefreshTokenRequest(BaseModel):
    """
    Token 刷新请求模型

    使用有效的刷新令牌换取新的访问令牌和刷新令牌对。
    """
    refresh_token: str = Field(..., description="刷新令牌")


class TokenResponse(BaseModel):
    """
    Token 响应模型

    登录或刷新成功后返回的令牌信息，包含访问令牌和刷新令牌。
    前端应将访问令牌用于 API 请求认证，刷新令牌用于令牌续期。
    """
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")


class TokenPayload(BaseModel):
    """
    Token 载荷模型

    定义 JWT 令牌解码后的载荷结构，用于类型安全的令牌内容访问。
    对应 security.py 中 create_access_token / create_refresh_token 生成的 payload。
    """
    sub: str = Field(..., description="用户 ID")
    type: str = Field(..., description="令牌类型")
    exp: int = Field(..., description="过期时间")
    iat: int = Field(..., description="签发时间")
