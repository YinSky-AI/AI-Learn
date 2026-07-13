# -*- coding: utf-8 -*-
"""
Alembic 环境配置
支持异步数据库迁移
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 导入所有模型以确保 Base.metadata 包含完整的表定义
from app.models import Base
from app.core.config import settings

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
target_metadata = Base.metadata

# 覆盖数据库 URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    以 'offline' 模式运行迁移
    仅生成 SQL 脚本，不连接数据库
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    以 'online' 模式运行异步迁移
    连接数据库并执行迁移
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """以 'online' 模式运行迁移的入口"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
