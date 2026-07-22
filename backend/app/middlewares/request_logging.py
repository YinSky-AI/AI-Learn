"""
请求日志中间件模块

记录每个 HTTP 请求的处理时间、状态码、请求方法和路径，
并在响应头中注入 X-Process-Time 便于客户端性能监控。

异常请求也会被记录，包括异常类型和处理耗时，便于排查慢请求和错误。

该中间件应尽早注册到 FastAPI 应用，以确保能捕获后续中间件和路由的处理时间。
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.observability import correlation

# 使用 "app.request" 命名空间的日志记录器，便于独立配置请求日志输出格式和目标
logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    继承自 Starlette 的 BaseHTTPMiddleware，记录每个 HTTP 请求的完整生命周期：
    - 正常响应：记录 INFO 级别日志，包含方法、路径、状态码、耗时、客户端 IP
    - 异常响应：记录 ERROR 级别日志，包含异常信息

    同时在响应头中设置 X-Process-Time，便于前端和负载均衡器监控接口延迟。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        处理每个传入请求并记录日志

        Args:
            request: Starlette 请求对象
            call_next: 调用下一个中间件或路由处理器的函数

        Returns:
            Response: Starlette 响应对象（携带 X-Process-Time 头）

        Raises:
            Exception: 将异常继续向上抛出，同时记录错误日志
        """
        start_time = time.time()
        context = correlation()

        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code} - "
                f"{process_time:.3f}s - request_id={context['request_id']} run_id={context['run_id']}"
            )
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            return response
        except Exception as exc:
            process_time = time.time() - start_time
            logger.error(
                f"{request.method} {request.url.path} - ERROR - "
                f"{process_time:.3f}s - request_id={context['request_id']} run_id={context['run_id']} error_type={type(exc).__name__}"
            )
            raise
