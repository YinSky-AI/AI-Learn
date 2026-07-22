"""集中式管理后台身份、签名会话与撤销服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import hashlib
import hmac
import json
import secrets
from typing import Callable
import uuid

import bcrypt
from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.core.security import verify_password
from app.models.user import User


SESSION_COOKIE_NAME = "admin_session"
CSRF_COOKIE_NAME = "admin_csrf"
LOGIN_CSRF_COOKIE_NAME = "admin_login_csrf"
SESSION_KEY_PREFIX = "admin:session:v1:"
SIGNING_KEY_NAME = "admin:session-signing-key:v1"

_DUMMY_PASSWORD_HASH = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@dataclass(frozen=True)
class AdminPrincipal:
    """已经由数据库角色和 Redis 会话共同确认的管理员主体。"""

    user_id: uuid.UUID
    session_id: str
    csrf_token: str
    expires_at: int


@dataclass(frozen=True)
class IssuedAdminSession:
    token: str
    csrf_token: str
    expires_at: int


class AdminAuthService:
    """管理后台唯一可信身份边界；Redis 不可用时安全地拒绝访问。"""

    def __init__(
        self,
        *,
        session_factory=AsyncSessionLocal,
        redis=redis_client,
        clock: Callable[[], datetime] | None = None,
        session_ttl_seconds: int | None = None,
        cookie_secure: bool | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.redis = redis
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.session_ttl_seconds = (
            session_ttl_seconds
            if session_ttl_seconds is not None
            else settings.ADMIN_SESSION_TTL_SECONDS
        )
        self.cookie_secure = (
            cookie_secure
            if cookie_secure is not None
            else settings.ADMIN_COOKIE_SECURE
        )

    async def authenticate(self, identifier: str, password: str) -> User | None:
        """验证当前有效管理员；失败结果不区分账号、密码或角色原因。"""

        normalized = identifier.strip()
        async with self.session_factory() as session:
            result = await session.execute(
                select(User).where(
                    User.email == normalized,
                    User.deleted_at.is_(None),
                )
            )
            user = result.scalar_one_or_none()
            password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
            password_matches = verify_password(password, password_hash)
            if user is None or not password_matches or not user.is_admin:
                return None
            return user

    async def create_session(self, user: User) -> IssuedAdminSession:
        now = int(self.clock().timestamp())
        expires_at = now + self.session_ttl_seconds
        session_id = secrets.token_urlsafe(24)
        csrf_token = secrets.token_urlsafe(32)
        payload = {
            "exp": expires_at,
            "iat": now,
            "role": "admin",
            "sid": session_id,
            "sub": str(user.id),
            "v": 1,
        }
        encoded_payload = _b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signing_key = await self._signing_key()
        signature = _b64encode(
            hmac.new(signing_key, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        )
        record = json.dumps(
            {
                "csrf": csrf_token,
                "exp": expires_at,
                "sub": str(user.id),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        await self.redis.client.set(
            self._session_key(session_id),
            record,
            ex=self.session_ttl_seconds,
        )
        return IssuedAdminSession(
            token=f"{encoded_payload}.{signature}",
            csrf_token=csrf_token,
            expires_at=expires_at,
        )

    async def validate_session(self, token: str | None) -> AdminPrincipal | None:
        payload = await self._verified_payload(token)
        if payload is None:
            return None
        try:
            expires_at = int(payload["exp"])
            user_id = uuid.UUID(payload["sub"])
            session_id = str(payload["sid"])
        except (KeyError, TypeError, ValueError):
            return None
        if (
            payload.get("v") != 1
            or payload.get("role") != "admin"
            or expires_at <= int(self.clock().timestamp())
        ):
            return None

        raw_record = await self.redis.get(self._session_key(session_id))
        if not raw_record:
            return None
        try:
            record = json.loads(raw_record)
            csrf_token = str(record["csrf"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if record.get("sub") != str(user_id) or record.get("exp") != expires_at:
            return None

        async with self.session_factory() as session:
            result = await session.execute(
                select(User.id).where(
                    User.id == user_id,
                    User.is_admin.is_(True),
                    User.deleted_at.is_(None),
                )
            )
            if result.scalar_one_or_none() is None:
                return None
        return AdminPrincipal(
            user_id=user_id,
            session_id=session_id,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )

    async def revoke_session(self, token: str | None) -> bool:
        payload = await self._verified_payload(token)
        if payload is None or not isinstance(payload.get("sid"), str):
            return False
        await self.redis.delete(self._session_key(payload["sid"]))
        return True

    async def rotate_signing_key(self) -> None:
        """轮换签名密钥会立即使全部既有管理会话失效。"""

        await self.redis.client.set(SIGNING_KEY_NAME, secrets.token_urlsafe(48))
        logger.bind(audit_event="admin_session_key_rotated").warning(
            "admin_audit event=admin_session_key_rotated result=success"
        )

    async def _verified_payload(self, token: str | None) -> dict | None:
        if not token or token.count(".") != 1 or len(token) > 4096:
            return None
        encoded_payload, supplied_signature = token.split(".", 1)
        try:
            signing_key = await self._signing_key()
            expected_signature = _b64encode(
                hmac.new(
                    signing_key,
                    encoded_payload.encode("ascii"),
                    hashlib.sha256,
                ).digest()
            )
            if not hmac.compare_digest(expected_signature, supplied_signature):
                return None
            payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
        except (UnicodeError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    async def _signing_key(self) -> bytes:
        key = await self.redis.get(SIGNING_KEY_NAME)
        if not key:
            candidate = secrets.token_urlsafe(48)
            await self.redis.client.set(SIGNING_KEY_NAME, candidate, nx=True)
            key = await self.redis.get(SIGNING_KEY_NAME)
        if not key:
            raise RuntimeError("管理会话存储不可用")
        return str(key).encode("utf-8")

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"{SESSION_KEY_PREFIX}{session_id}"
