# -*- coding: utf-8 -*-
"""
FastAPI 应用入口模块

该模块是智慧学习平台后端服务的启动入口，负责：
- 创建和配置 FastAPI 应用实例
- 注册 CORS、请求日志、速率限制等中间件
- 注册 API 路由和全局异常处理器
- 管理应用生命周期（启动/关闭时的资源初始化和清理）

包含的中间件：
- CORS 中间件：处理跨域请求
- 请求日志中间件：记录请求处理时间和状态码
- 请求 ID 中间件：为每个请求分配唯一追踪 ID
- 速率限制中间件：基于 Redis 滑动窗口的 API 限流
"""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from loguru import logger

from app.core.config import settings
from app.core.redis import redis_client
from app.core.database import engine
from app.models import Base
from app.api.v1.router import router as v1_router
from app.admin.routes import router as admin_router
from app.middlewares import add_exception_handlers, RequestLoggingMiddleware


# ============ 速率限制中间件（基于 Redis 滑动窗口）============

async def rate_limit_middleware(request: Request, call_next):
    """
    API 速率限制中间件

    基于 Redis 有序集合实现滑动窗口算法，限制每个客户端每分钟的最大请求次数。
    当请求超过阈值时返回 429 状态码，并添加 CORS 头避免浏览器跨域错误。
    Redis 不可用时自动降级，不阻止请求。

    Args:
        request: FastAPI 请求对象
        call_next: 调用下一个中间件或路由处理器的函数

    Returns:
        Response: FastAPI 响应对象（可能被限流拦截）
    """
    # 跳过健康检查、文档路径和管理后台
    skip_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
    if request.url.path in skip_paths or request.url.path.startswith("/admin"):
        return await call_next(request)

    # 获取客户端标识（优先使用用户ID，否则使用 IP）
    client_id = request.headers.get("X-Client-ID") or request.client.host
    key = f"rate:{client_id}"

    try:
        current_time = time.time()
        window_start = current_time - 60  # 60秒窗口

        # 使用 Redis 有序集合实现滑动窗口
        now = f"{current_time:.3f}"
        await redis_client.client.zadd(key, {now: current_time})
        # 清理窗口外的记录
        await redis_client.client.zremrangebyscore(key, 0, window_start)
        # 统计窗口内请求数
        count = await redis_client.client.zcard(key)

        if count > settings.RATE_LIMIT_PER_MINUTE:
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "code": "RATE_001",
                    "message": f"请求过于频繁，请稍后再试（限制：每分钟{settings.RATE_LIMIT_PER_MINUTE}次）",
                    "data": None,
                    "meta": None,
                },
            )
            # 添加 CORS 头，避免浏览器报跨域错误
            origin = request.headers.get("origin")
            if origin and origin in settings.CORS_ORIGINS:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
            elif "*" in settings.CORS_ALLOW_METHODS:
                response.headers["Access-Control-Allow-Origin"] = "*"
            return response

        # 设置 key 过期时间
        await redis_client.client.expire(key, 120)
    except Exception as e:
        # Redis 不可用时不阻止请求，仅记录日志
        logger.warning(f"速率限制检查失败（已跳过）: {e}")

    return await call_next(request)


# ============ 请求 ID 中间件 ============

async def request_id_middleware(request: Request, call_next):
    """
    请求 ID 中间件

    为每个 HTTP 请求分配唯一追踪 ID，优先从请求头 X-Request-ID 获取，
    否则自动生成 UUID。请求 ID 会注入到请求状态并在响应头中返回，
    便于日志追踪和问题排查。

    Args:
        request: FastAPI 请求对象
        call_next: 调用下一个中间件或路由处理器的函数

    Returns:
        Response: 携带 X-Request-ID 响应头的 FastAPI 响应对象
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ============ 应用生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器

    使用异步上下文管理器管理应用的启动和关闭过程：
    - 启动阶段：自动创建数据库表、初始化 Redis 连接
    - 关闭阶段：安全关闭 Redis 连接

    数据库创建失败和 Redis 连接失败时仅记录警告日志，不会阻止应用启动，
    确保服务具备降级运行能力。

    Args:
        app: FastAPI 应用实例

    Yields:
        None: 应用运行期间控制权交给 FastAPI
    """
    # 启动
    logger.info("正在启动智慧学习平台 API...")
    logger.info(f"版本: {settings.APP_VERSION}")
    logger.info(f"调试模式: {settings.DEBUG}")

    # 自动创建数据库表（开发环境）
    try:
        async with engine.begin() as conn:
            # 多 worker 会并行触发生命周期；用事务级 PostgreSQL 锁串行化建表，
            # 避免两个 create_all 同时创建同名复合类型/表。
            await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('learning_platform_schema'))"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表检查/创建完成")
    except Exception as e:
        logger.warning(f"数据库表创建失败（可能已存在）: {e}")

    try:
        await redis_client.init()
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.warning(f"Redis 连接失败（将使用降级模式）: {e}")

    yield

    # 关闭
    logger.info("正在关闭智慧学习平台 API...")
    try:
        await redis_client.close()
        logger.info("Redis 连接已关闭")
    except Exception:
        pass
    logger.info("应用已关闭")


# ============ 创建 FastAPI 应用 ============

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============ 注册中间件 ============

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# 注册请求日志中间件
app.add_middleware(RequestLoggingMiddleware)
# 注册全局异常处理器
add_exception_handlers(app)

# 自定义中间件
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(request_id_middleware)

# ============ 注册路由 ============

# 管理后台路由（放在中间件之前注册，确保可用）
app.include_router(admin_router)

app.include_router(v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/test-error-dict", include_in_schema=False)
async def test_error_dict():
    """触发字典详情的 HTTP 异常，供错误响应回归测试使用。"""
    raise HTTPException(status_code=500, detail={"message": "服务暂时不可用"})


# ============ 健康检查端点 ============

@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查端点

    返回服务基本运行状态信息，供负载均衡器健康探活和监控系统使用。
    该端点已被速率限制中间件跳过，确保探活请求不会被限流。

    Returns:
        dict: 包含应用名称、版本和运行状态的标准化响应
    """
    return {
        "code": "SUCCESS",
        "message": "服务运行正常",
        "data": {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "healthy",
        },
        "meta": None,
    }


@app.get("/", tags=["系统"])
async def root():
    """
    根路径端点

    返回 API 的基本信息，包括应用名称、版本号、文档地址和 API 前缀，
    便于前端或第三方服务快速了解 API 概况。

    Returns:
        dict: 包含 API 基本信息和文档链接的标准化响应
    """
    return {
        "code": "SUCCESS",
        "message": f"欢迎使用 {settings.APP_NAME}",
        "data": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "api_prefix": settings.API_V1_PREFIX,
        },
        "meta": None,
    }
