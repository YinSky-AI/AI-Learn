# -*- coding: utf-8 -*-
"""
FastAPI 应用入口
包含 CORS 配置、路由注册、中间件、异常处理、生命周期管理
"""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from loguru import logger

from app.core.config import settings
from app.core.redis import redis_client
from app.core.database import engine
from app.models import Base
from app.api.v1.router import router as v1_router


# ============ 速率限制中间件（基于 Redis 滑动窗口）============

async def rate_limit_middleware(request: Request, call_next):
    """
    API 速率限制中间件
    基于 Redis 滑动窗口算法，每分钟最多 N 次请求
    跳过健康检查等不需要限流的路径
    """
    # 跳过健康检查和文档路径
    skip_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
    if request.url.path in skip_paths:
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
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "code": "RATE_001",
                    "message": f"请求过于频繁，请稍后再试（限制：每分钟{settings.RATE_LIMIT_PER_MINUTE}次）",
                    "data": None,
                    "meta": None,
                },
            )

        # 设置 key 过期时间
        await redis_client.client.expire(key, 120)
    except Exception as e:
        # Redis 不可用时不阻止请求，仅记录日志
        logger.warning(f"速率限制检查失败（已跳过）: {e}")

    return await call_next(request)


# ============ 请求 ID 中间件 ============

async def request_id_middleware(request: Request, call_next):
    """
    为每个请求分配唯一 ID
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ============ 全局异常处理器 ============

async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理
    捕获未处理的异常，返回结构化错误响应
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        f"[{request_id}] 未处理的异常: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "SYS_001",
            "message": "服务器内部错误，请稍后重试",
            "data": None,
            "meta": {"request_id": request_id},
        },
    )


async def validation_exception_handler(request: Request, exc: Exception):
    """
    参数校验异常处理
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(f"[{request_id}] 参数校验失败: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VAL_001",
            "message": f"请求参数校验失败: {str(exc)}",
            "data": None,
            "meta": {"request_id": request_id},
        },
    )


# ============ 应用生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时初始化 Redis，关闭时清理资源
    """
    # 启动
    logger.info("正在启动智慧学习平台 API...")
    logger.info(f"版本: {settings.APP_VERSION}")
    logger.info(f"调试模式: {settings.DEBUG}")

    # 自动创建数据库表（开发环境）
    try:
        async with engine.begin() as conn:
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

# 自定义中间件
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(request_id_middleware)

# ============ 注册全局异常处理器 ============

app.add_exception_handler(Exception, global_exception_handler)

# ============ 注册路由 ============

app.include_router(v1_router, prefix=settings.API_V1_PREFIX)


# ============ 健康检查端点 ============

@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查端点
    用于负载均衡器和监控探活
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
    根路径
    返回 API 基本信息
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
