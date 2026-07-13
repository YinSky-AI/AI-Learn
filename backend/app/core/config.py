# -*- coding: utf-8 -*-
"""
应用配置管理模块
使用 pydantic-settings 从环境变量加载配置
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置"""

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
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # ============ 速率限制配置 ============
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # ============ AI 服务配置（DeepSeek） ============
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    AI_MODEL_NAME: str = "deepseek-chat"
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.7


# 全局配置单例
settings = Settings()
