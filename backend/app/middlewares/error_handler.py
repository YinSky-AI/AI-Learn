"""全局异常处理"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
import logging

from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)


def add_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning(f"HTTP {exc.status_code}: {exc.detail} - {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                data=None,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        message = errors[0]["msg"] if errors else "请求参数验证失败"
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
        logger.error(f"Unhandled exception: {exc} - {request.url.path}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ApiResponse(
                code="INTERNAL_ERROR",
                message="服务器内部错误，请稍后重试",
                data=None,
            ).model_dump(),
        )
