# -*- coding: utf-8 -*-
"""
数据库连接管理模块
提供 SQLAlchemy 异步引擎、会话工厂和基类
"""

import uuid
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话依赖
    用法: async with get_db() as session: ...
    或在 FastAPI 中: Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class BaseModel:
    """
    SQLAlchemy 模型基类
    提供 UUID 主键、创建/更新时间戳
    """

    # UUID 主键，默认使用 uuid_generate_v4()
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("uuid_generate_v4()"),
    )

    # 创建时间
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        default=datetime.utcnow,
    )

    # 更新时间
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=datetime.utcnow,
    )


class SoftDeleteModel(BaseModel):
    """
    支持软删除的模型基类
    包含 deleted_at 字段
    """

    # 软删除时间，非 None 表示已删除
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)
