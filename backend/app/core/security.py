# -*- coding: utf-8 -*-
"""
安全模块

提供用户认证相关的安全功能，包括：
- 密码哈希：使用 bcrypt 算法对密码进行单向哈希和验证
- JWT 令牌：生成和验证访问令牌（Access Token）及刷新令牌（Refresh Token）

安全设计：
- 密码使用 bcrypt 加盐哈希，每次哈希生成不同的盐值
- JWT 访问令牌短期有效（默认 30 分钟），降低泄露风险
- JWT 刷新令牌长期有效（默认 7 天），用于无感刷新访问令牌
- 刷新令牌包含唯一 jti 标识，支持后续令牌吊销扩展
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from app.core.config import settings


# ============ 密码处理 ============

def hash_password(password: str) -> str:
    """
    对明文密码进行 bcrypt 哈希

    使用 bcrypt 算法生成随机盐值并对密码进行单向哈希，
    哈希结果包含算法版本、成本因子和盐值，可直接存储到数据库。

    Args:
        password: 用户输入的明文密码

    Returns:
        str: bcrypt 密码哈希字符串，可直接存入数据库
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希是否匹配

    使用 bcrypt 的 checkpw 函数安全地比较明文密码和存储的哈希值。
    任何异常（如哈希格式错误）都会安全地返回 False，不会泄露信息。

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的 bcrypt 哈希值

    Returns:
        bool: 密码匹配返回 True，不匹配或异常返回 False
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ============ JWT Token 处理 ============

def create_access_token(
    user_id: uuid.UUID,
    credential_version: int = 1,
    extra_data: Optional[dict] = None,
) -> str:
    """
    创建 JWT 访问令牌

    生成短期有效的访问令牌，用于认证受保护 API 的请求。
    令牌类型为 "access"，仅能被需要认证的接口接受。

    Args:
        user_id: 用户唯一标识符
        extra_data: 额外自定义载荷数据，可选

    Returns:
        str: 编码后的 JWT 访问令牌字符串

    Note:
        有效期由 settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES 控制（默认 30 分钟）
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "ver": credential_version,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra_data:
        payload.update(extra_data)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: uuid.UUID,
    credential_version: int = 1,
    extra_data: Optional[dict] = None,
) -> str:
    """
    创建 JWT 刷新令牌

    生成长期有效的刷新令牌，用于在访问令牌过期后获取新的访问令牌，
    实现无感登录体验。令牌包含唯一 jti 标识，为未来实现令牌吊销提供基础。

    Args:
        user_id: 用户唯一标识符
        extra_data: 额外自定义载荷数据，可选

    Returns:
        str: 编码后的 JWT 刷新令牌字符串

    Note:
        有效期由 settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS 控制（默认 7 天）
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "ver": credential_version,
        "jti": str(uuid.uuid4()),  # JWT ID，用于吊销
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    }
    if extra_data:
        payload.update(extra_data)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    解码并验证 JWT Token

    解析 JWT 字符串并验证签名和过期时间。
    支持访问令牌和刷新令牌的通用解码。

    Args:
        token: JWT 令牌字符串

    Returns:
        dict: JWT 载荷（payload），包含 sub、type、exp、iat 等字段

    Raises:
        ValueError: Token 已过期或 Token 无效（签名错误、格式错误等）
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token 已过期")
    except jwt.InvalidTokenError:
        raise ValueError("Token 无效")


def get_token_user_id(token: str) -> uuid.UUID:
    """
    从 Token 中提取用户 ID

    便捷函数，先解码 Token 再从 sub 字段提取用户 UUID。

    Args:
        token: JWT 令牌字符串

    Returns:
        uuid.UUID: Token 所属用户的唯一标识符

    Raises:
        ValueError: Token 无效、已过期或 sub 字段缺失/格式错误
    """
    payload = decode_token(token)
    return uuid.UUID(payload["sub"])
