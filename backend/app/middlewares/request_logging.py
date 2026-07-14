"""请求日志中间件"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的处理时间和状态码"""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        client_host = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code} - "
                f"{process_time:.3f}s - {client_host}"
            )
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            return response
        except Exception as exc:
            process_time = time.time() - start_time
            logger.error(
                f"{request.method} {request.url.path} - ERROR - "
                f"{process_time:.3f}s - {client_host} - {exc}"
            )
            raise
