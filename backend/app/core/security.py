# -*- coding: utf-8 -*-
"""
安全模块
提供 JWT Token 生成/验证、密码哈希处理
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
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希是否匹配
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
    extra_data: Optional[dict] = None,
) -> str:
    """
    创建 JWT 访问令牌
    有效期: JWT_ACCESS_TOKEN_EXPIRE_MINUTES 分钟
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra_data:
        payload.update(extra_data)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: uuid.UUID,
    extra_data: Optional[dict] = None,
) -> str:
    """
    创建 JWT 刷新令牌
    有效期: JWT_REFRESH_TOKEN_EXPIRE_DAYS 天
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
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
    成功返回 payload，失败抛出异常
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
    """
    payload = decode_token(token)
    return uuid.UUID(payload["sub"])
