"""
全局异常处理中间件模块

为 FastAPI 应用注册统一的异常处理器，将所有异常转换为结构化的 ApiResponse 格式返回。
涵盖的异常类型：
- StarletteHTTPException: FastAPI/Starlette 抛出的 HTTP 异常（如 404、403）
- RequestValidationError: 请求参数校验失败（如 Pydantic 验证错误）
- Exception: 所有未被捕获的服务器内部异常

所有异常均记录到日志，便于问题排查和监控告警。
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
import logging

from app.schemas.common import ApiResponse

# 模块级日志记录器，用于记录异常处理过程中的日志
logger = logging.getLogger(__name__)


def user_message(detail: object, fallback: str) -> str:
    """将异常详情转换为可安全展示给用户的纯文本。"""
    if isinstance(detail, dict):
        return str(detail.get("message") or fallback)
    return str(detail) if isinstance(detail, str) else fallback


def add_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器

    为 FastAPI 应用实例注册三类异常处理器，确保所有异常都能被捕获并返回
    统一格式的 JSON 响应。

    Args:
        app: FastAPI 应用实例

    Note:
        该函数应在应用启动时调用一次，通常在 main.py 中完成注册。
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """
        处理 Starlette HTTP 异常

        捕获如 404 Not Found、403 Forbidden 等 HTTP 异常，
        记录警告日志并返回包含状态码的标准化响应。
        """
        logger.warning(f"HTTP {exc.status_code}: {exc.detail} - {request.url.path}")

        # 提取用户友好的错误信息
        # exc.detail 可能是 str 或 dict（FastAPI HTTPException 支持 dict）
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", f"HTTP_{exc.status_code}")
            message = user_message(exc.detail, "请求失败")
        else:
            code = f"HTTP_{exc.status_code}"
            message = user_message(exc.detail, "请求失败")

        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse(
                code=code,
                message=message,
                data=None,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        处理请求参数校验异常

        捕获 Pydantic 模型验证失败、请求体格式错误等，
        提取第一条错误信息记录日志，并返回详细的校验错误列表。
        """
        errors = exc.errors()
        detail = errors[0].get("msg") if errors else None
        message = user_message(detail, "请求参数验证失败")
        logger.warning(f"Validation error: {message} - {request.url.path}")
        return JSONResponse(
            status_code=422,
            content=ApiResponse(
                code="VALIDATION_ERROR",
                message=message,
                data={"errors": errors},
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        处理所有未被捕获的异常

        作为最后一道防线，捕获所有未被特定处理器处理的异常。
        记录完整错误堆栈到日志，但向客户端返回友好的错误提示，避免泄露内部信息。
        """
        logger.error(f"Unhandled exception: {exc} - {request.url.path}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ApiResponse(
                code="INTERNAL_ERROR",
                message=user_message(None, "服务暂时不可用，请稍后重试"),
                data=None,
            ).model_dump(),
        )
