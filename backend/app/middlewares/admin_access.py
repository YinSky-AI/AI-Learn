"""管理后台统一认证、CSRF 与审计中间件。"""

from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.admin_auth import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME


UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
PUBLIC_ADMIN_PATHS = frozenset({"/admin/login"})


def _is_api_or_write(request: Request) -> bool:
    return "/api/" in request.url.path or request.method in UNSAFE_METHODS


def _target_type(path: str) -> str:
    relative = path.removeprefix("/admin/")
    return relative.split("/", 1)[0] or "dashboard"


class AdminAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/admin") or path in PUBLIC_ADMIN_PATHS:
            return await call_next(request)

        service = request.app.state.admin_auth_service
        token = request.cookies.get(SESSION_COOKIE_NAME)
        try:
            principal = await service.validate_session(token)
        except Exception as exc:
            logger.bind(audit_event="admin_session_rejected").warning(
                "admin_audit event=admin_session_rejected reason=store_unavailable "
                "error_type={}",
                type(exc).__name__,
            )
            principal = None
        if principal is None:
            logger.bind(audit_event="admin_session_rejected").warning(
                "admin_audit event=admin_session_rejected reason=invalid_session "
                "request_id={}",
                getattr(request.state, "request_id", "unassigned"),
            )
            if _is_api_or_write(request):
                return PlainTextResponse("未登录或会话已过期", status_code=401)
            return RedirectResponse("/admin/login", status_code=302)

        request.state.admin_principal = principal
        request.state.admin_csrf_token = principal.csrf_token

        if request.method in UNSAFE_METHODS and path != "/admin/logout":
            supplied_csrf = request.headers.get("X-CSRF-Token", "")
            if not hmac.compare_digest(supplied_csrf, principal.csrf_token):
                logger.bind(audit_event="admin_csrf_rejected").warning(
                    "admin_audit event=admin_csrf_rejected actor_id={} method={} "
                    "target_type={} request_id={}",
                    principal.user_id,
                    request.method,
                    _target_type(path),
                    getattr(request.state, "request_id", "unassigned"),
                )
                return PlainTextResponse(
                    "安全校验失败，请刷新页面后重试",
                    status_code=403,
                )

        response = await call_next(request)
        response.set_cookie(
            CSRF_COOKIE_NAME,
            principal.csrf_token,
            max_age=service.session_ttl_seconds,
            secure=service.cookie_secure,
            httponly=False,
            samesite="strict",
            path="/admin",
        )
        if request.method in UNSAFE_METHODS:
            logger.bind(audit_event="admin_write").info(
                "admin_audit event=admin_write actor_id={} method={} target_type={} "
                "status={} request_id={}",
                principal.user_id,
                request.method,
                _target_type(path),
                response.status_code,
                getattr(request.state, "request_id", "unassigned"),
            )
        return response
