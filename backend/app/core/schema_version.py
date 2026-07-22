"""Schema revision 状态检查与迁移目标安全边界。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import urlsplit

from sqlalchemy import text


NON_PRODUCTION_ENVIRONMENTS = {"local", "ci", "test"}
RELEASE_ENVIRONMENTS = NON_PRODUCTION_ENVIRONMENTS | {"staging", "production"}
DISPOSABLE_DATABASE_SUFFIXES = ("_test", "_restore", "_recovery")
EXPECTED_REVISIONS = {
    "primary": "lp_0003_admin_recovery",
    "question-bank": "catalog_0002_admin_recovery",
}
VERSION_TABLES = {
    "primary": "alembic_version_learning",
    "question-bank": "alembic_version_catalog",
}


class SchemaVersionError(RuntimeError):
    """可直接显示给运维执行者的脱敏 Schema 错误。"""


@dataclass(frozen=True)
class MigrationTarget:
    """不携带连接凭据的已核验数据库目标。"""

    alias: str
    host: str
    database: str
    environment: str
    disposable: bool


@dataclass(frozen=True)
class SchemaRevisionStatus:
    """数据库当前 revision 与应用期望 revision 的比较结果。"""

    current_revision: str | None
    expected_revision: str
    compatible: bool
    message: str


def _target_setting(settings: dict[str, str], target_alias: str) -> str:
    try:
        return settings[target_alias]
    except KeyError as exc:
        raise SchemaVersionError("Schema 目标别名必须是 primary 或 question-bank") from exc


def get_expected_schema_revision(target_alias: str) -> str:
    """返回随应用发布的单一批准 head。"""

    return _target_setting(EXPECTED_REVISIONS, target_alias)


def get_schema_version_table(target_alias: str) -> str:
    """返回各数据库互不共享的 Alembic 版本表。"""

    return _target_setting(VERSION_TABLES, target_alias)


def validate_migration_target(
    database_url: str,
    *,
    target_alias: str,
    environment: str,
    expected_host: str,
    expected_database: str,
    allow_release: bool = False,
) -> MigrationTarget:
    """仅允许与二次确认一致的非生产、主业务可丢弃数据库。"""

    parsed = urlsplit(database_url)
    host = parsed.hostname or ""
    database = parsed.path.lstrip("/")
    if not host or not database:
        raise SchemaVersionError("迁移目标缺少有效 host 或 database")
    if target_alias not in {"primary", "question-bank"}:
        raise SchemaVersionError("迁移目标别名必须是 primary 或 question-bank")
    if target_alias == "primary" and not database.startswith("learning_platform"):
        raise SchemaVersionError(
            "主业务库 revision 只允许 learning_platform 命名空间，"
            "禁止应用到题库或其他数据库"
        )
    if target_alias == "question-bank" and not database.startswith("ai_learn"):
        raise SchemaVersionError("题库 revision 禁止应用到主业务库")
    if environment not in RELEASE_ENVIRONMENTS:
        raise SchemaVersionError("迁移 environment 不在批准枚举内")
    if host != expected_host or database != expected_database:
        raise SchemaVersionError("迁移连接与二次确认的 host/database 目标不一致")
    disposable = database.endswith(DISPOSABLE_DATABASE_SUFFIXES)
    if disposable and environment not in NON_PRODUCTION_ENVIRONMENTS:
        raise SchemaVersionError("可丢弃迁移只允许 local、ci、test 非生产环境")
    if not disposable and not allow_release:
        raise SchemaVersionError(
            "目标不是可丢弃数据库；普通数据库只能通过"
            "带审批与备份证明的发布路径迁移"
        )
    return MigrationTarget(
        alias=target_alias,
        host=host,
        database=database,
        environment=environment,
        disposable=disposable,
    )


def validate_test_database_target(
    database_url: str,
    environment: str,
) -> tuple[str, str, str]:
    """复用迁移边界，只允许 postgres-test 上以 _test 结尾的已知测试库。"""

    parsed = urlsplit(database_url)
    host = parsed.hostname or ""
    database = parsed.path.lstrip("/")
    if host != "postgres-test" or not database.endswith("_test"):
        raise SchemaVersionError(
            "后端测试只允许 local/ci 环境中的 postgres-test/*_test 可丢弃测试数据库"
        )
    if database.startswith("learning_platform"):
        target_alias = "primary"
    elif database.startswith("ai_learn"):
        target_alias = "question-bank"
    else:
        raise SchemaVersionError("测试数据库不属于批准的 primary 或 question-bank 命名空间")
    try:
        target = validate_migration_target(
            database_url,
            target_alias=target_alias,
            environment=environment,
            expected_host="postgres-test",
            expected_database=database,
        )
    except SchemaVersionError as exc:
        raise SchemaVersionError(
            "后端测试只允许 local/ci 环境中的 postgres-test/*_test 可丢弃测试数据库"
        ) from exc
    if environment not in {"local", "ci"}:
        raise SchemaVersionError(
            "后端测试只允许 local/ci 环境中的 postgres-test/*_test 可丢弃测试数据库"
        )
    return target.host, target.database, target.environment


def evaluate_schema_revision(
    current_revision: str | None,
    expected_revision: str,
) -> SchemaRevisionStatus:
    """生成不含连接信息的 Schema 兼容状态。"""

    if current_revision == expected_revision:
        return SchemaRevisionStatus(
            current_revision=current_revision,
            expected_revision=expected_revision,
            compatible=True,
            message=f"Schema revision 已就绪：{expected_revision}",
        )
    if current_revision is None:
        message = (
            "数据库尚未纳入版本管理；请先在已核验目标运行批准的 Alembic 迁移，"
            f"期望 revision={expected_revision}"
        )
    else:
        message = (
            "Schema 版本不匹配："
            f"current={current_revision} expected={expected_revision}"
        )
    return SchemaRevisionStatus(
        current_revision=current_revision,
        expected_revision=expected_revision,
        compatible=False,
        message=message,
    )


def enforce_schema_revision(
    status: SchemaRevisionStatus,
    *,
    policy: str,
    legacy_contract_validated: bool = False,
) -> SchemaRevisionStatus:
    """严格模式阻断错版；warn 模式仅返回状态且绝不修改数据库。"""

    if policy not in {"strict", "warn"}:
        raise SchemaVersionError("Schema 版本策略必须是 strict 或 warn")
    if policy == "strict" and not status.compatible:
        raise SchemaVersionError(f"Schema 版本不匹配，应用拒绝启动：{status.message}")
    if policy == "warn" and not status.compatible:
        if status.current_revision is not None:
            raise SchemaVersionError(
                "warn 不允许已版本化但陈旧的 Schema：" + status.message
            )
        if not legacy_contract_validated:
            raise SchemaVersionError("warn 未完成 legacy contract 验证，应用拒绝启动")
    return status


async def read_current_schema_revision(engine: Any, target_alias: str) -> str | None:
    """只读查询指定数据库的独立 Alembic 版本表。"""

    version_table = get_schema_version_table(target_alias)
    async with engine.connect() as connection:
        exists_result = await connection.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": f"public.{version_table}"},
        )
        if not exists_result.scalar_one():
            return None
        rows = (
            await connection.execute(
                text(f'SELECT version_num FROM "{version_table}"')
            )
        ).scalars().all()
    if len(rows) > 1:
        raise SchemaVersionError(f"{target_alias} 存在多个 revision head")
    return rows[0] if rows else None


async def verify_schema_targets(
    engines: Mapping[str, Any],
    *,
    policy: str,
    revision_reader: Callable[[Any, str], Awaitable[str | None]] = read_current_schema_revision,
) -> list[SchemaRevisionStatus]:
    """在应用启动前只读核验主业务库和题库各自的 head。"""

    required_aliases = ("primary", "question-bank")
    if set(engines) != set(required_aliases):
        raise SchemaVersionError("启动必须同时核验 primary 与 question-bank Schema")
    statuses: list[SchemaRevisionStatus] = []
    for target_alias in required_aliases:
        statuses.append(
            await verify_schema_target(
                engines[target_alias],
                target_alias,
                policy=policy,
                revision_reader=revision_reader,
            )
        )
    return statuses


async def verify_schema_target(
    engine: Any,
    target_alias: str,
    *,
    policy: str,
    revision_reader: Callable[[Any, str], Awaitable[str | None]] = read_current_schema_revision,
    legacy_validator: Callable[[Any, str], Awaitable[None]] | None = None,
) -> SchemaRevisionStatus:
    """只读核验单个显式数据库目标，供导入/运维命令复用。"""

    try:
        current = await revision_reader(engine, target_alias)
    except SchemaVersionError:
        raise
    except Exception as exc:
        raise SchemaVersionError(
            f"{target_alias} Schema 版本读取失败，操作已停止"
        ) from exc
    status = evaluate_schema_revision(
        current,
        get_expected_schema_revision(target_alias),
    )
    legacy_contract_validated = False
    if policy == "warn" and current is None:
        validator = legacy_validator or validate_unversioned_legacy_schema
        await validator(engine, target_alias)
        legacy_contract_validated = True
    if policy == "strict" and not status.compatible:
        raise SchemaVersionError(f"{target_alias}：{status.message}")
    return enforce_schema_revision(
        status,
        policy=policy,
        legacy_contract_validated=legacy_contract_validated,
    )


async def validate_unversioned_legacy_schema(engine: Any, target_alias: str) -> None:
    """warn 仅允许结构完整匹配 legacy contract 的未版本库。"""

    from schema_admin import validate_legacy_schema

    try:
        async with engine.connect() as connection:
            await connection.run_sync(
                lambda sync_connection: validate_legacy_schema(
                    sync_connection, target_alias
                )
            )
    except SchemaVersionError:
        raise
    except Exception as exc:
        raise SchemaVersionError(
            f"{target_alias} 未版本基线结构验证失败，应用拒绝启动"
        ) from exc
