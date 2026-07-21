# -*- coding: utf-8 -*-
"""
应用配置管理模块

使用 pydantic-settings 从环境变量和 .env 文件加载应用配置，
提供类型安全、默认值支持的全局配置单例。

配置优先级（从高到低）：
1. 环境变量
2. .env 文件
3. 字段默认值

包含的配置类别：
- 应用基础配置（名称、版本、调试模式）
- 数据库配置（PostgreSQL 异步连接池）
- Redis 配置（缓存和限流）
- JWT 配置（认证令牌生成与验证）
- CORS 配置（跨域资源共享）
- 速率限制配置（API 限流参数）
- AI 服务配置（DeepSeek API 调用参数）
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用全局配置类

    继承自 pydantic_settings.BaseSettings，自动从环境变量和 .env 文件读取配置。
    所有配置项均提供默认值，生产环境应通过环境变量覆盖敏感信息（如密钥、密码）。

    Attributes:
        APP_NAME: 应用名称，用于 API 文档和响应展示
        APP_VERSION: 应用版本号，遵循语义化版本规范
        DEBUG: 调试模式开关，开启后输出详细错误信息
        API_V1_PREFIX: V1 API 路由前缀
        DATABASE_URL: 异步 PostgreSQL 连接字符串
        JWT_SECRET_KEY: JWT 签名密钥，生产环境必须修改
        DEEPSEEK_API_KEY: DeepSeek AI 服务 API 密钥
        RATE_LIMIT_PER_MINUTE: 每分钟最大请求数限制
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ============ 应用基础配置 ============
    APP_NAME: str = "智慧学习平台 API"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "面向6-18岁学生的AI自适应学习平台"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ============ 数据库配置 ============
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/learning_platform"
    AI_LEARN_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_learn"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ============ Redis 配置 ============
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # ============ JWT 配置 ============
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ============ CORS 配置 ============
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost/admin",
        "http://localhost:80",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # ============ 速率限制配置 ============
    RATE_LIMIT_PER_MINUTE: int = 200
    RATE_LIMIT_BURST: int = 30

    # ============ AI 服务配置（DeepSeek） ============
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    AI_MODEL_NAME: str = "deepseek-chat"
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.7


# 全局配置单例
settings = Settings()
