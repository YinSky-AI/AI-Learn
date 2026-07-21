# -*- coding: utf-8 -*-
"""
数据库连接管理模块

提供 SQLAlchemy 异步数据库连接基础设施，包括：
- 异步数据库引擎（支持 PostgreSQL + asyncpg）
- 异步会话工厂和依赖注入函数
- 模型基类（包含 UUID 主键、时间戳、软删除等通用字段）

该模块是数据持久层的核心，所有 SQLAlchemy 模型均继承自此处定义的基类。
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

# ai_learn 题库数据库引擎（管理后台题库）
ai_learn_engine = create_async_engine(
    settings.AI_LEARN_DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
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

# ai_learn 会话工厂
AI_LearnAsyncSessionLocal = async_sessionmaker(
    ai_learn_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话依赖

    异步生成器函数，用于在 FastAPI 路由中通过 Depends 注入数据库会话，
    或在非路由代码中通过 async with 获取会话。
    自动管理事务提交、回滚和连接关闭。

    Args:
        无（通过 AsyncSessionLocal 内部创建会话）

    Yields:
        AsyncSession: SQLAlchemy 异步数据库会话

    Raises:
        Exception: 数据库操作异常时会自动回滚并重新抛出

    Usage:
        # FastAPI 路由中
        async def my_route(db: AsyncSession = Depends(get_db)): ...

        # 普通异步代码中
        async with get_db() as session: ...
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
    SQLAlchemy 模型基类（混入类）

    为所有数据模型提供通用字段，包括 UUID 主键和自动时间戳。
    该基类不包含 SQLAlchemy 的 DeclarativeBase，需与 models.Base 联合使用：
    `class MyModel(BaseModel, Base): ...`

    Attributes:
        id: UUID 主键，数据库端使用 uuid_generate_v4() 生成
        created_at: 记录创建时间，不可为空
        updated_at: 记录最后更新时间，onupdate 自动更新
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
    支持软删除的模型基类（混入类）

    继承自 BaseModel，额外提供 deleted_at 软删除字段。
    删除记录时不从数据库物理删除，而是设置 deleted_at 时间戳。
    查询时需显式过滤 deleted_at is None 以排除已删除记录。

    Attributes:
        deleted_at: 软删除时间戳，None 表示未删除，非 None 表示已删除
    """

    # 软删除时间，非 None 表示已删除
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)
