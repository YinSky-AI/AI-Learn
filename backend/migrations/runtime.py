"""两个 Alembic root 共用的脱敏运行时配置。"""

from __future__ import annotations

import os
from typing import Callable

from alembic import context
from sqlalchemy import MetaData, engine_from_config, pool
from sqlalchemy.engine import make_url


def _sync_url() -> str:
    raw_url = os.getenv("DATABASE_URL", "")
    if not raw_url:
        raise RuntimeError("缺少迁移数据库连接配置")
    try:
        return make_url(raw_url).set(drivername="postgresql+psycopg2").render_as_string(
            hide_password=False
        )
    except Exception as exc:
        raise RuntimeError("迁移数据库连接配置格式无效") from exc


def run_migrations(
    *,
    target_alias: str,
    target_metadata: MetaData,
    version_table: str,
    include_object: Callable[..., bool] | None = None,
) -> None:
    """只允许由安全 Adapter 核验过的在线事务迁移。"""

    if os.getenv("MIGRATION_TARGET_VERIFIED") != target_alias:
        raise RuntimeError("迁移目标尚未通过安全 Adapter 二次核验")
    if context.is_offline_mode():
        raise RuntimeError("禁止离线生成 SQL；迁移必须连接已核验目标")

    external_connection = context.config.attributes.get("connection")

    def execute(connection) -> None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=version_table,
            compare_type=True,
            include_object=include_object,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    if external_connection is not None:
        execute(external_connection)
        return

    configuration = context.config.get_section(context.config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        execute(connection)
