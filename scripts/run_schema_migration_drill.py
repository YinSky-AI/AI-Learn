"""在固定的四个 tmpfs 数据库中演练双 Alembic root 与基线采用。"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent.parent
ACCEPTANCE_ROOT = ROOT / "test" / "acceptance" / "P0-07"
RUNTIME_ROOT = ROOT / "test" / ".runtime" / "P0-07"
DRILL_SECRET_ROOT = RUNTIME_ROOT / "drill-secrets"
SOURCE_HOST = "postgres-test"
PRIMARY_SOURCE_DATABASE = "learning_platform_test"
CATALOG_SOURCE_DATABASE = "ai_learn_test"
RESTORE_HOST = "postgres-restore"
PRIMARY_RESTORE_DATABASE = "learning_platform_restore"
CATALOG_RESTORE_DATABASE = "ai_learn_restore"
PRIMARY_BOOTSTRAP_DATABASE = "learning_platform_bootstrap"
CATALOG_BOOTSTRAP_DATABASE = "ai_learn_bootstrap"
ENVIRONMENT = os.getenv("DELIVERY_TEST_ENV", "local")
BACKEND_PROBE_CONTAINER = "ai-learn-schema-drill-backend"

PRIMARY_HEAD = "lp_0016_node_code_comment"
PRIMARY_BASELINE = "lp_0001_legacy_baseline"
CATALOG_HEAD = "catalog_0002_admin_recovery"
PERSISTENT_HOST = "postgres"
PERSISTENT_PRIMARY_DATABASE = "learning_platform"
PERSISTENT_CATALOG_DATABASE = "ai_learn"
_TMPFS_DATABASE_PASSWORD: str | None = None
PRIMARY_MANAGED_TABLES = (
    "achievements", "admin_change_audits", "age_groups", "answers", "chat_messages", "courses",
    "daily_challenge_answers", "daily_challenge_attempts",
    "daily_challenge_questions", "daily_challenges", "error_logs",
    "evolution_records", "gamification_events", "generated_question_batches", "generation_jobs",
    "generated_questions", "harness_runs", "knowledge_nodes",
    "learning_sessions", "lessons", "question_quality_checks", "questions",
    "session_memories", "skills", "subjects", "tool_call_logs",
    "user_achievements", "user_courses", "user_lessons", "users",
    "wrong_question_events", "wrong_questions",
)
CATALOG_MANAGED_TABLES = (
    "admin_change_audits", "knowledge_points", "question_knowledge", "question_stats", "questions",
)


class SchemaMigrationDrillError(RuntimeError):
    """可直接显示给演练执行者的脱敏失败。"""


def redact(value: str) -> str:
    value = re.sub(
        r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^\s:/@]+):[^\s@]+@",
        r"\g<scheme>\g<user>:***@",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"(?i)(password\s*[=:]\s*)[^\s]+", r"\1***", value)


def assert_no_secret_material(
    *,
    stage: str,
    payload: str,
    secret_values: tuple[str, ...],
) -> None:
    for secret_value in secret_values:
        if secret_value and secret_value in payload:
            raise SchemaMigrationDrillError(f"{stage} 泄露数据库凭据或完整 DSN")


def validate_schema_drill_targets(
    *,
    source_host: str,
    primary_source_database: str,
    catalog_source_database: str,
    restore_host: str,
    primary_restore_database: str,
    catalog_restore_database: str,
    environment: str,
) -> None:
    expected = (
        SOURCE_HOST,
        PRIMARY_SOURCE_DATABASE,
        CATALOG_SOURCE_DATABASE,
        RESTORE_HOST,
        PRIMARY_RESTORE_DATABASE,
        CATALOG_RESTORE_DATABASE,
    )
    actual = (
        source_host,
        primary_source_database,
        catalog_source_database,
        restore_host,
        primary_restore_database,
        catalog_restore_database,
    )
    if actual != expected or environment not in {"local", "ci"}:
        raise SchemaMigrationDrillError(
            "Schema 演练只允许固定的四个可丢弃 tmpfs 数据库"
        )


def assert_revision_observation(
    *,
    stage: str,
    actual: str | None,
    expected: str | None,
    managed_table_count: int,
) -> dict[str, Any]:
    """只从数据库实际查询结果生成 revision 证据。"""

    if actual != expected:
        raise SchemaMigrationDrillError(
            f"{stage} revision 不匹配：actual={actual or 'base'} "
            f"expected={expected or 'base'}"
        )
    if expected is None and managed_table_count != 0:
        raise SchemaMigrationDrillError(f"{stage} 到 base 后仍有受管理表")
    return {
        "revision": actual or "base",
        "managed_table_count": managed_table_count,
    }


def parse_tmpfs_mounts(payload: str) -> set[str]:
    """根据 Docker inspect 实际 mount 生成 tmpfs 证据。"""

    try:
        mounts = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SchemaMigrationDrillError("无法解析 Docker tmpfs mount 证据") from exc
    if not isinstance(mounts, dict):
        raise SchemaMigrationDrillError("无法解析 Docker tmpfs mount 证据")
    host_tmpfs = (mounts.get("HostConfig") or {}).get("Tmpfs") or {}
    destinations = set(host_tmpfs)
    destinations.update(
        str(mount.get("Destination"))
        for mount in mounts.get("Mounts", [])
        if isinstance(mount, dict) and mount.get("Type") == "tmpfs"
    )
    if "/var/lib/postgresql/data" not in destinations:
        raise SchemaMigrationDrillError("PostgreSQL 演练数据目录不是 tmpfs")
    return destinations


def _container_id(service: str) -> str:
    result = _compose("ps", "-q", service, stage=f"查询 {service} 容器", echo=False)
    container_id = result.stdout.strip()
    if not container_id:
        raise SchemaMigrationDrillError(f"{service} 容器未运行")
    return container_id


def _verify_tmpfs_storage(service: str) -> dict[str, Any]:
    container_id = _container_id(service)
    result = _run(
        ["docker", "inspect", container_id, "--format", "{{json .}}"],
        stage=f"核验 {service} tmpfs mount",
        echo=False,
    )
    destinations = parse_tmpfs_mounts(result.stdout.strip())
    return {
        "container_id_prefix": container_id[:12],
        "data_mount_type": "tmpfs",
        "data_mount": "/var/lib/postgresql/data",
        "tmpfs_destinations": sorted(destinations),
    }


def _service_is_running(service: str) -> bool:
    result = subprocess.run(
        ["docker", "compose", "ps", "-q", "--status", "running", service],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _run(
    command: list[str],
    *,
    stage: str,
    input_text: str | None = None,
    echo: bool = True,
    expect_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        input=input_text,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )
    output = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part.strip()
    )
    if expect_failure:
        if result.returncode == 0:
            raise SchemaMigrationDrillError(f"{stage}本应拒绝执行但返回成功")
        if echo and output:
            print(redact(output))
        return result
    if result.returncode:
        detail = redact(output)
        if len(detail) > 1600:
            detail = detail[-1600:]
        raise SchemaMigrationDrillError(f"{stage}失败：{detail or '命令未提供诊断'}")
    if echo and output:
        print(redact(output))
    return result


def _compose(*arguments: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return _run(["docker", "compose", *arguments], **kwargs)


def _psql(service: str, database: str, sql: str, *, echo: bool = False) -> str:
    result = _compose(
        "exec",
        "-T",
        service,
        "psql",
        "--no-password",
        "--tuples-only",
        "--no-align",
        "--set",
        "ON_ERROR_STOP=1",
        "--username",
        "postgres",
        "--dbname",
        database,
        stage=f"{service}/{database} 数据库查询",
        input_text=sql,
        echo=echo,
    )
    return result.stdout.strip()


def _ensure_database(service: str, database: str) -> None:
    exists = _psql(
        service,
        "postgres",
        f"SELECT 1 FROM pg_database WHERE datname = '{database}';",
    )
    if exists != "1":
        _compose(
            "exec",
            "-T",
            service,
            "createdb",
            "--username",
            "postgres",
            database,
            stage=f"创建可丢弃数据库 {service}/{database}",
        )


def _read_secret_file(path_value: str | None, label: str) -> str:
    if not path_value:
        raise SchemaMigrationDrillError(f"缺少 {label} secret 文件路径")
    path = Path(path_value)
    if not path.is_absolute() or path.is_symlink():
        raise SchemaMigrationDrillError(f"{label} 必须是绝对非符号链接文件")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise SchemaMigrationDrillError(f"{label} secret 文件不可读") from exc
    if len(lines) != 1 or not lines[0]:
        raise SchemaMigrationDrillError(f"{label} secret 必须是非空单行文件")
    return lines[0]


def _database_url(host: str, database: str) -> str:
    if _TMPFS_DATABASE_PASSWORD is None:
        raise SchemaMigrationDrillError("tmpfs 数据库凭据尚未初始化")
    encoded_password = quote(_TMPFS_DATABASE_PASSWORD, safe="")
    return (
        "postgresql+asyncpg://postgres:"
        f"{encoded_password}@{host}:5432/{database}"
    )


def _database_url_secret_path(alias: str) -> Path:
    filename = (
        "primary_database_url" if alias == "primary" else "catalog_database_url"
    )
    return DRILL_SECRET_ROOT / filename


def _write_database_url_secret(alias: str, host: str, database: str) -> Path:
    path = _database_url_secret_path(alias)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_database_url(host, database) + "\n", encoding="utf-8")
    return path


def _schema_admin(
    *,
    action: str,
    alias: str,
    host: str,
    database: str,
    revision: str | None = None,
    allow_baseline: bool = False,
    allow_destructive: bool = False,
    allow_release: bool = False,
    approval_reference: str | None = None,
    confirm_empty_bootstrap: bool = False,
    expect_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    url_file = _write_database_url_secret(alias, host, database)
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "--no-deps",
        "backend",
        "python",
        "schema_admin.py",
        action,
        "--target",
        alias,
        "--database-url-file",
        "/run/secrets/primary_database_url"
        if alias == "primary"
        else "/run/secrets/catalog_database_url",
        "--environment",
        ENVIRONMENT,
        "--expected-host",
        host,
        "--expected-database",
        database,
    ]
    if revision:
        command.extend(("--revision", revision))
    if allow_baseline:
        command.append("--allow-baseline-adoption")
    if allow_destructive:
        command.append("--allow-destructive-downgrade")
    if allow_release:
        command.append("--allow-release")
    if approval_reference:
        command.extend(("--approval-reference", approval_reference))
    if confirm_empty_bootstrap:
        command.append("--confirm-empty-bootstrap")
    if not url_file.is_file():
        raise SchemaMigrationDrillError("Schema URL secret 文件未创建")
    return _run(
        command,
        stage=f"{alias} {action} {database}",
        expect_failure=expect_failure,
    )


def _revision(host: str, database: str, version_table: str) -> str | None:
    exists = _psql(
        host,
        database,
        f"SELECT to_regclass('public.{version_table}') IS NOT NULL;",
    )
    if exists != "t":
        return None
    result = _psql(
        host, database, f'SELECT version_num FROM "{version_table}" LIMIT 1;'
    )
    return result or None


def _sql_array(values: tuple[str, ...]) -> str:
    return "ARRAY[" + ",".join("'" + value + "'" for value in values) + "]::text[]"


def _managed_table_count(
    host: str,
    database: str,
    managed_tables: tuple[str, ...],
) -> int:
    value = _psql(
        host,
        database,
        "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public' "
        f"AND tablename = ANY({_sql_array(managed_tables)});",
    )
    return int(value)


def content_digest(table_row_hashes: dict[str, list[str]]) -> str:
    """对表和行哈希排序，生成与物理行顺序无关的内容摘要。"""

    lines = [
        f"{table_name}|{row_hash}"
        for table_name in sorted(table_row_hashes)
        for row_hash in sorted(table_row_hashes[table_name])
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _database_fingerprint(
    host: str,
    database: str,
    *,
    managed_tables: tuple[str, ...],
    version_table: str,
    head_revision: str,
) -> dict[str, Any]:
    """对精确受管表、列/default/约束/索引和全表行数做确定性摘要。"""

    table_array = _sql_array(managed_tables)
    actual_tables = {
        line
        for line in _psql(
            host,
            database,
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            f"AND tablename = ANY({table_array}) ORDER BY tablename;",
        ).splitlines()
        if line
    }
    revision = _revision(host, database, version_table)
    all_managed_tables = set(managed_tables)
    if revision == head_revision and actual_tables != all_managed_tables:
        missing = sorted(all_managed_tables - actual_tables)
        raise SchemaMigrationDrillError(
            "完整 Schema 指纹缺少受管理表：" + ",".join(missing)
        )
    expected_tables = actual_tables
    structure_rows = _psql(
        host,
        database,
        f"""
WITH managed(name) AS (SELECT unnest({table_array}))
SELECT item FROM (
  SELECT 'column|' || c.relname || '|' || a.attnum || '|' || a.attname || '|' ||
         format_type(a.atttypid, a.atttypmod) || '|' || a.attnotnull || '|' ||
         COALESCE(pg_get_expr(d.adbin, d.adrelid), '') AS item
  FROM pg_class c
  JOIN pg_namespace n ON n.oid=c.relnamespace
  JOIN managed m ON m.name=c.relname
  JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
  LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
  WHERE n.nspname='public'
  UNION ALL
  SELECT 'constraint|' || c.relname || '|' || con.conname || '|' || con.contype::text || '|' ||
         pg_get_constraintdef(con.oid, true)
  FROM pg_constraint con
  JOIN pg_class c ON c.oid=con.conrelid
  JOIN pg_namespace n ON n.oid=c.relnamespace
  JOIN managed m ON m.name=c.relname
  WHERE n.nspname='public'
  UNION ALL
  SELECT 'index|' || tablename || '|' || indexname || '|' || indexdef
  FROM pg_indexes i JOIN managed m ON m.name=i.tablename
  WHERE schemaname='public'
) contract ORDER BY item;
""",
    )
    count_lines = _psql(
        host,
        database,
        "SELECT format('SELECT %L || ''|'' || COUNT(*) FROM public.%I;', "
        "tablename, tablename) FROM pg_tables WHERE schemaname='public' "
        f"AND tablename = ANY({table_array}) ORDER BY tablename\n\\gexec\n",
    )
    counts: dict[str, int] = {}
    for line in count_lines.splitlines():
        if "|" not in line:
            continue
        table_name, count = line.rsplit("|", 1)
        if table_name in expected_tables:
            counts[table_name] = int(count)
    if set(counts) != expected_tables:
        raise SchemaMigrationDrillError("代表性数据摘要未覆盖全部受管理表")
    table_row_hashes = {
        table_name: [
            row_hash
            for row_hash in _psql(
                host,
                database,
                f"SELECT md5(to_jsonb(row_value)::text) "
                f"FROM public.\"{table_name}\" row_value ORDER BY 1;",
            ).splitlines()
            if row_hash
        ]
        for table_name in actual_tables
    }
    business_row_hashes = {
        table_name: [
            row_hash
            for row_hash in _psql(
                host,
                database,
                f"SELECT md5((to_jsonb(row_value) - 'deleted_at')::text) "
                f"FROM public.\"{table_name}\" row_value ORDER BY 1;",
            ).splitlines()
            if row_hash
        ]
        for table_name in actual_tables
        if table_name != "admin_change_audits"
    }
    data_rows = "\n".join(f"{name}|{counts[name]}" for name in sorted(counts))
    return {
        "managed_table_count": len(actual_tables),
        "managed_tables": sorted(actual_tables),
        "revision": revision or "unversioned",
        "schema_sha256": hashlib.sha256(structure_rows.encode("utf-8")).hexdigest(),
        "table_row_counts": counts,
        "data_sha256": hashlib.sha256(data_rows.encode("utf-8")).hexdigest(),
        "content_sha256": content_digest(table_row_hashes),
        "business_content_sha256": content_digest(business_row_hashes),
    }


def _primary_fingerprint(host: str, database: str) -> dict[str, Any]:
    return _database_fingerprint(
        host,
        database,
        managed_tables=PRIMARY_MANAGED_TABLES,
        version_table="alembic_version_learning",
        head_revision=PRIMARY_HEAD,
    )


def _catalog_fingerprint(host: str, database: str) -> dict[str, Any]:
    return _database_fingerprint(
        host,
        database,
        managed_tables=CATALOG_MANAGED_TABLES,
        version_table="alembic_version_catalog",
        head_revision=CATALOG_HEAD,
    )


def _backup_tool_command(runtime_dir: Path, *arguments: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--profile",
        "delivery-test",
        "run",
        "--rm",
        "--no-deps",
        "--volume",
        f"{runtime_dir.resolve().as_posix()}:/run/secrets:ro",
        "--volume",
        f"{ACCEPTANCE_ROOT.resolve().as_posix()}:/evidence",
        "backup-tool",
        *arguments,
    ]


def _encrypted_backup_restore(
    *,
    label: str,
    source_host: str,
    source_database: str,
    target_database: str,
    fingerprint: Any,
    source_password_secret: str,
) -> dict[str, Any]:
    primary_dir = ACCEPTANCE_ROOT / "backups" / label / "primary"
    replica_dir = ACCEPTANCE_ROOT / "backups" / label / "replica"
    primary_dir.mkdir(parents=True, exist_ok=True)
    replica_dir.mkdir(parents=True, exist_ok=True)
    before = set(primary_dir.glob("*.manifest.json"))
    source_before = fingerprint(source_host, source_database)
    _run(
        _backup_tool_command(
            RUNTIME_ROOT,
            "backup",
            "--source-host",
            source_host,
            "--source-database",
            source_database,
            "--environment",
            ENVIRONMENT,
            "--source-password-file",
            f"/run/secrets/{source_password_secret}",
            "--key-file",
            "/run/secrets/backup_key",
            "--backup-dir",
            f"/evidence/backups/{label}/primary",
            "--replica-dir",
            f"/evidence/backups/{label}/replica",
            "--replica-domain",
            "local-schema-drill-copy",
            "--allow-same-device-rehearsal",
        ),
        stage=f"{label} AES-GCM 备份",
    )
    created = sorted(set(primary_dir.glob("*.manifest.json")) - before)
    if len(created) != 1:
        raise SchemaMigrationDrillError(f"{label} 备份未产生唯一清单")
    manifest_path = created[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive = primary_dir / str(manifest.get("archive", ""))
    if not archive.is_file():
        raise SchemaMigrationDrillError(f"{label} 加密备份产物不存在")
    _run(
        _backup_tool_command(
            RUNTIME_ROOT,
            "restore",
            "--archive",
            f"/evidence/backups/{label}/primary/{archive.name}",
            "--manifest",
            f"/evidence/backups/{label}/primary/{manifest_path.name}",
            "--key-file",
            "/run/secrets/backup_key",
            "--target-host",
            RESTORE_HOST,
            "--target-database",
            target_database,
            "--target-environment",
            ENVIRONMENT,
            "--target-password-file",
            "/run/secrets/tmpfs_postgres_password",
        ),
        stage=f"{label} 隔离恢复",
    )
    restored_before_adoption = fingerprint(RESTORE_HOST, target_database)
    source_after = fingerprint(source_host, source_database)
    if source_before != source_after:
        raise SchemaMigrationDrillError(f"{label} 备份恢复改变了源库 Schema/数据摘要")
    if source_before != restored_before_adoption:
        raise SchemaMigrationDrillError(f"{label} 恢复库与只读源库 Schema/数据摘要不一致")
    return {
        "manifest": str(manifest_path.relative_to(ROOT)).replace("\\", "/"),
        "encryption": manifest.get("encryption"),
        "sha256": manifest.get("sha256"),
        "source_fingerprint_before": source_before,
        "restored_fingerprint_before_adoption": restored_before_adoption,
        "source_fingerprint_after": source_after,
        "source_unchanged": source_before == source_after,
        "restore_matches_source": source_before == restored_before_adoption,
    }


def _start_strict_backend(
    *,
    primary_host: str,
    primary_database: str,
    catalog_host: str,
    catalog_database: str,
) -> dict[str, Any]:
    _write_database_url_secret("primary", primary_host, primary_database)
    _write_database_url_secret("question-bank", catalog_host, catalog_database)
    if _container_exists(BACKEND_PROBE_CONTAINER):
        _run(
            ["docker", "rm", "-f", BACKEND_PROBE_CONTAINER],
            stage="清理旧 Schema 健康探针",
            echo=False,
        )
    command = [
        "docker",
        "compose",
        "run",
        "-d",
        "--no-deps",
        "--name",
        BACKEND_PROBE_CONTAINER,
        "-e",
        "SCHEMA_VERSION_POLICY=strict",
        "backend",
    ]
    _run(command, stage="strict 双库应用启动")
    try:
        inspect_result = _run(
            ["docker", "inspect", BACKEND_PROBE_CONTAINER],
            stage="strict 应用容器 metadata 脱敏检查",
            echo=False,
        )
        assert_no_secret_material(
            stage="strict 应用容器 metadata",
            payload=inspect_result.stdout,
            secret_values=(
                _TMPFS_DATABASE_PASSWORD or "",
                _database_url(primary_host, primary_database),
                _database_url(catalog_host, catalog_database),
            ),
        )
        deadline = time.monotonic() + 35
        health_payload = ""
        while time.monotonic() < deadline:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    BACKEND_PROBE_CONTAINER,
                    "curl",
                    "-fsS",
                    "http://localhost:8000/health",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                health_payload = result.stdout.strip()
                break
            time.sleep(1)
        if not health_payload or '"healthy"' not in health_payload:
            log_result = _run(
                ["docker", "logs", BACKEND_PROBE_CONTAINER],
                stage="读取 strict 应用日志",
                echo=False,
            )
            logs = f"{log_result.stdout}\n{log_result.stderr}"
            raise SchemaMigrationDrillError(
                "strict 应用未达到 healthy：" + redact(logs[-1000:])
            )
        log_result = _run(
            ["docker", "logs", BACKEND_PROBE_CONTAINER],
            stage="读取 strict 应用日志",
            echo=False,
        )
        logs = f"{log_result.stdout}\n{log_result.stderr}"
        if PRIMARY_HEAD not in logs or CATALOG_HEAD not in logs:
            raise SchemaMigrationDrillError("strict 应用日志缺少两个批准 revision")
        api_result = _run(
            [
                "docker", "exec", BACKEND_PROBE_CONTAINER, "curl", "-fsS",
                "http://localhost:8000/api/v1/content/subjects",
            ],
            stage="strict 数据库关键 API",
            echo=False,
        )
        try:
            api_payload = json.loads(api_result.stdout)
        except json.JSONDecodeError as exc:
            raise SchemaMigrationDrillError("strict 数据库 API 未返回有效 JSON") from exc
        if api_payload.get("code") != "SUCCESS" or not isinstance(
            api_payload.get("data"), list
        ):
            raise SchemaMigrationDrillError("strict 数据库 API 响应契约不合格")
        return {
            "targets": {
                "primary": f"{primary_host}/{primary_database}",
                "question_bank": f"{catalog_host}/{catalog_database}",
            },
            "health": json.loads(health_payload),
            "database_backed_api": {
                "path": "/api/v1/content/subjects",
                "code": api_payload["code"],
                "item_count": len(api_payload["data"]),
            },
            "revision_logs_present": True,
            "container_metadata_contains_database_secret": False,
        }
    finally:
        _run(
            ["docker", "rm", "-f", BACKEND_PROBE_CONTAINER],
            stage="停止 strict 应用探针",
            echo=False,
        )


def _container_exists(name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", name],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _strict_start_rejected(*, stage: str, expected_diagnostic: str) -> bool:
    _write_database_url_secret(
        "primary", SOURCE_HOST, PRIMARY_SOURCE_DATABASE
    )
    _write_database_url_secret(
        "question-bank", SOURCE_HOST, CATALOG_SOURCE_DATABASE
    )
    result = _run(
        [
            "docker", "compose", "run", "--rm", "--no-deps",
            "-e", "SCHEMA_VERSION_POLICY=strict", "backend",
        ],
        stage=stage,
        expect_failure=True,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if expected_diagnostic not in output:
        raise SchemaMigrationDrillError(f"{stage}缺少清晰纯文本诊断")
    return True


def _reject_strict_unversioned() -> bool:
    _schema_admin(
        action="downgrade",
        alias="question-bank",
        host=SOURCE_HOST,
        database=CATALOG_SOURCE_DATABASE,
        revision="base",
        allow_destructive=True,
    )
    rejected = _strict_start_rejected(
        stage="strict 未版本启动拒绝",
        expected_diagnostic="尚未纳入版本管理",
    )
    _schema_admin(
        action="upgrade",
        alias="question-bank",
        host=SOURCE_HOST,
        database=CATALOG_SOURCE_DATABASE,
    )
    return rejected


def _reject_strict_stale() -> bool:
    _schema_admin(
        action="downgrade",
        alias="primary",
        host=SOURCE_HOST,
        database=PRIMARY_SOURCE_DATABASE,
        revision=PRIMARY_BASELINE,
        allow_destructive=True,
    )
    rejected = _strict_start_rejected(
        stage="strict 真正 stale revision 启动拒绝",
        expected_diagnostic=f"current={PRIMARY_BASELINE} expected={PRIMARY_HEAD}",
    )
    _schema_admin(
        action="upgrade",
        alias="primary",
        host=SOURCE_HOST,
        database=PRIMARY_SOURCE_DATABASE,
    )
    return rejected


def _compose_release_bootstrap(
    alias: str,
    database: str,
    *,
    expect_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    _write_database_url_secret(alias, SOURCE_HOST, database)
    service = (
        "schema-bootstrap-primary"
        if alias == "primary"
        else "schema-bootstrap-catalog"
    )
    return _compose(
        "--profile",
        "schema-bootstrap",
        "run",
        "--rm",
        "--no-deps",
        "-e",
        "SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE=CHG-P0-07-BOOTSTRAP",
        "-e",
        f"SCHEMA_TARGET_HOST={SOURCE_HOST}",
        "-e",
        f"SCHEMA_TARGET_DATABASE={database}",
        service,
        stage=f"{alias} 普通空库 Compose bootstrap",
        expect_failure=expect_failure,
    )


def _compose_release_bootstrap_all() -> dict[str, str]:
    _compose_release_bootstrap("primary", PRIMARY_BOOTSTRAP_DATABASE)
    _compose_release_bootstrap("question-bank", CATALOG_BOOTSTRAP_DATABASE)
    primary_revision = _revision(
        SOURCE_HOST,
        PRIMARY_BOOTSTRAP_DATABASE,
        "alembic_version_learning",
    )
    catalog_revision = _revision(
        SOURCE_HOST,
        CATALOG_BOOTSTRAP_DATABASE,
        "alembic_version_catalog",
    )
    if primary_revision != PRIMARY_HEAD or catalog_revision != CATALOG_HEAD:
        raise SchemaMigrationDrillError("双库普通空库 bootstrap 未到达批准 head")
    return {
        "primary": primary_revision,
        "question_bank": catalog_revision,
    }


def run_drill() -> dict[str, Any]:
    global _TMPFS_DATABASE_PASSWORD
    validate_schema_drill_targets(
        source_host=SOURCE_HOST,
        primary_source_database=PRIMARY_SOURCE_DATABASE,
        catalog_source_database=CATALOG_SOURCE_DATABASE,
        restore_host=RESTORE_HOST,
        primary_restore_database=PRIMARY_RESTORE_DATABASE,
        catalog_restore_database=CATALOG_RESTORE_DATABASE,
        environment=ENVIRONMENT,
    )
    print(
        "Schema 演练写入目标已二次核验："
        f"fixture={SOURCE_HOST}/({PRIMARY_SOURCE_DATABASE},{CATALOG_SOURCE_DATABASE}) "
        f"restore={RESTORE_HOST}/({PRIMARY_RESTORE_DATABASE},{CATALOG_RESTORE_DATABASE}) "
        f"environment={ENVIRONMENT}"
    )
    ACCEPTANCE_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    DRILL_SECRET_ROOT.mkdir(parents=True, exist_ok=True)
    _TMPFS_DATABASE_PASSWORD = secrets.token_urlsafe(24)
    persistent_password = (
        _read_secret_file(
            os.getenv("PERSISTENT_POSTGRES_PASSWORD_FILE"),
            "持久 PostgreSQL 密码",
        )
        if ENVIRONMENT == "local"
        else _TMPFS_DATABASE_PASSWORD
    )
    (RUNTIME_ROOT / "backup_key").write_bytes(secrets.token_bytes(32))
    tmpfs_password_file = RUNTIME_ROOT / "tmpfs_postgres_password"
    persistent_password_file = RUNTIME_ROOT / "persistent_postgres_password"
    tmpfs_password_file.write_text(_TMPFS_DATABASE_PASSWORD + "\n", encoding="utf-8")
    persistent_password_file.write_text(persistent_password + "\n", encoding="utf-8")
    primary_url_file = _write_database_url_secret(
        "primary", SOURCE_HOST, PRIMARY_SOURCE_DATABASE
    )
    catalog_url_file = _write_database_url_secret(
        "question-bank", SOURCE_HOST, CATALOG_SOURCE_DATABASE
    )
    secret_environment = {
        "POSTGRES_PASSWORD_SECRET_FILE": str(tmpfs_password_file.resolve()),
        "PRIMARY_DATABASE_URL_SECRET_FILE": str(primary_url_file.resolve()),
        "CATALOG_DATABASE_URL_SECRET_FILE": str(catalog_url_file.resolve()),
    }
    previous_secret_environment = {
        key: os.environ.get(key) for key in secret_environment
    }
    os.environ.update(secret_environment)
    compose = ("--profile", "delivery-test")
    started_at = time.perf_counter()
    try:
        compose_config = _compose("config", stage="Compose secret metadata 检查", echo=False)
        assert_no_secret_material(
            stage="Compose config",
            payload=compose_config.stdout,
            secret_values=(
                _TMPFS_DATABASE_PASSWORD,
                _database_url(SOURCE_HOST, PRIMARY_SOURCE_DATABASE),
                _database_url(SOURCE_HOST, CATALOG_SOURCE_DATABASE),
            ),
        )
        _compose(
            *compose, "build", "backend", "backup-tool",
            "schema-bootstrap-primary", "schema-bootstrap-catalog",
            stage="演练镜像构建",
        )
        _compose(
            *compose,
            "up",
            "-d",
            "--force-recreate",
            "--wait",
            SOURCE_HOST,
            RESTORE_HOST,
            stage="四目标 tmpfs PostgreSQL 启动",
        )
        _ensure_database(SOURCE_HOST, CATALOG_SOURCE_DATABASE)
        _ensure_database(RESTORE_HOST, CATALOG_RESTORE_DATABASE)
        _ensure_database(SOURCE_HOST, PRIMARY_BOOTSTRAP_DATABASE)
        _ensure_database(SOURCE_HOST, CATALOG_BOOTSTRAP_DATABASE)
        storage_evidence = {
            SOURCE_HOST: _verify_tmpfs_storage(SOURCE_HOST),
            RESTORE_HOST: _verify_tmpfs_storage(RESTORE_HOST),
        }

        _compose_release_bootstrap("primary", PRIMARY_BOOTSTRAP_DATABASE)
        primary_first_revision = _revision(
            SOURCE_HOST,
            PRIMARY_BOOTSTRAP_DATABASE,
            "alembic_version_learning",
        )
        if primary_first_revision != PRIMARY_HEAD:
            raise SchemaMigrationDrillError("主业务普通空库首次 bootstrap 未到达 head")
        _compose_release_bootstrap("primary", PRIMARY_BOOTSTRAP_DATABASE)
        _psql(
            SOURCE_HOST,
            CATALOG_BOOTSTRAP_DATABASE,
            "CREATE TABLE bootstrap_blocker(id integer);",
        )
        catalog_first = _compose_release_bootstrap(
            "question-bank",
            CATALOG_BOOTSTRAP_DATABASE,
            expect_failure=True,
        )
        if "备份" not in f"{catalog_first.stdout}\n{catalog_first.stderr}":
            raise SchemaMigrationDrillError("题库 bootstrap 失败缺少纯文本备份诊断")
        if _revision(
            SOURCE_HOST,
            CATALOG_BOOTSTRAP_DATABASE,
            "alembic_version_catalog",
        ) is not None:
            raise SchemaMigrationDrillError("题库 bootstrap 失败后残留 revision")
        if _revision(
            SOURCE_HOST,
            PRIMARY_BOOTSTRAP_DATABASE,
            "alembic_version_learning",
        ) != PRIMARY_HEAD:
            raise SchemaMigrationDrillError("题库失败破坏了已成功的主业务 bootstrap")
        _psql(
            SOURCE_HOST,
            CATALOG_BOOTSTRAP_DATABASE,
            "DROP TABLE bootstrap_blocker;",
        )
        primary_before_catalog_retry = _revision(
            SOURCE_HOST,
            PRIMARY_BOOTSTRAP_DATABASE,
            "alembic_version_learning",
        )
        catalog_single_entry_retry = _compose_release_bootstrap(
            "question-bank",
            CATALOG_BOOTSTRAP_DATABASE,
        )
        catalog_retry_revision = _revision(
            SOURCE_HOST,
            CATALOG_BOOTSTRAP_DATABASE,
            "alembic_version_catalog",
        )
        primary_after_catalog_retry = _revision(
            SOURCE_HOST,
            PRIMARY_BOOTSTRAP_DATABASE,
            "alembic_version_learning",
        )
        if catalog_single_entry_retry.returncode or catalog_retry_revision != CATALOG_HEAD:
            raise SchemaMigrationDrillError("题库单入口重试未到达批准 head")
        if (
            primary_before_catalog_retry != PRIMARY_HEAD
            or primary_after_catalog_retry != primary_before_catalog_retry
        ):
            raise SchemaMigrationDrillError("题库单入口重试改变了主业务库 revision")
        aggregate_repeat = _compose_release_bootstrap_all()

        cross_target = _schema_admin(
            action="upgrade",
            alias="primary",
            host=SOURCE_HOST,
            database=CATALOG_SOURCE_DATABASE,
            expect_failure=True,
        )
        if "题库" not in f"{cross_target.stdout}\n{cross_target.stderr}":
            raise SchemaMigrationDrillError("交叉应用虽被拒绝，但缺少清晰目标诊断")

        # 全新空库：零到 head。
        _schema_admin(
            action="upgrade",
            alias="primary",
            host=SOURCE_HOST,
            database=PRIMARY_SOURCE_DATABASE,
        )
        _schema_admin(
            action="upgrade",
            alias="question-bank",
            host=SOURCE_HOST,
            database=CATALOG_SOURCE_DATABASE,
        )
        primary_empty_head = _primary_fingerprint(
            SOURCE_HOST, PRIMARY_SOURCE_DATABASE
        )
        catalog_empty_head = _catalog_fingerprint(
            SOURCE_HOST, CATALOG_SOURCE_DATABASE
        )

        # primary lp_0002 -> lp_0001 -> base -> lp_0001 -> head，每步实查。
        _schema_admin(
            action="downgrade",
            alias="primary",
            host=SOURCE_HOST,
            database=PRIMARY_SOURCE_DATABASE,
            revision=PRIMARY_BASELINE,
            allow_destructive=True,
        )
        primary_at_baseline = assert_revision_observation(
            stage="primary lp_0002 -> lp_0001",
            actual=_revision(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE, "alembic_version_learning"
            ),
            expected=PRIMARY_BASELINE,
            managed_table_count=_managed_table_count(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE, PRIMARY_MANAGED_TABLES
            ),
        )
        _schema_admin(
            action="downgrade",
            alias="primary",
            host=SOURCE_HOST,
            database=PRIMARY_SOURCE_DATABASE,
            revision="base",
            allow_destructive=True,
        )
        primary_at_base = assert_revision_observation(
            stage="primary lp_0001 -> base",
            actual=_revision(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE, "alembic_version_learning"
            ),
            expected=None,
            managed_table_count=_managed_table_count(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE, PRIMARY_MANAGED_TABLES
            ),
        )
        _schema_admin(
            action="upgrade",
            alias="primary",
            host=SOURCE_HOST,
            database=PRIMARY_SOURCE_DATABASE,
            revision=PRIMARY_BASELINE,
        )
        primary_baseline_reapplied = assert_revision_observation(
            stage="primary base -> lp_0001",
            actual=_revision(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE, "alembic_version_learning"
            ),
            expected=PRIMARY_BASELINE,
            managed_table_count=_managed_table_count(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE, PRIMARY_MANAGED_TABLES
            ),
        )
        _schema_admin(
            action="upgrade",
            alias="primary",
            host=SOURCE_HOST,
            database=PRIMARY_SOURCE_DATABASE,
        )
        primary_head_reapplied = assert_revision_observation(
            stage="primary lp_0001 -> head",
            actual=_revision(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE, "alembic_version_learning"
            ),
            expected=PRIMARY_HEAD,
            managed_table_count=_managed_table_count(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE, PRIMARY_MANAGED_TABLES
            ),
        )
        _schema_admin(
            action="downgrade",
            alias="question-bank",
            host=SOURCE_HOST,
            database=CATALOG_SOURCE_DATABASE,
            revision="base",
            allow_destructive=True,
        )
        catalog_at_base = assert_revision_observation(
            stage="catalog baseline -> base",
            actual=_revision(
                SOURCE_HOST, CATALOG_SOURCE_DATABASE, "alembic_version_catalog"
            ),
            expected=None,
            managed_table_count=_managed_table_count(
                SOURCE_HOST, CATALOG_SOURCE_DATABASE, CATALOG_MANAGED_TABLES
            ),
        )
        _schema_admin(
            action="upgrade",
            alias="question-bank",
            host=SOURCE_HOST,
            database=CATALOG_SOURCE_DATABASE,
        )
        catalog_head_reapplied = assert_revision_observation(
            stage="catalog base -> head",
            actual=_revision(
                SOURCE_HOST, CATALOG_SOURCE_DATABASE, "alembic_version_catalog"
            ),
            expected=CATALOG_HEAD,
            managed_table_count=_managed_table_count(
                SOURCE_HOST, CATALOG_SOURCE_DATABASE, CATALOG_MANAGED_TABLES
            ),
        )
        strict_unversioned_rejected = _reject_strict_unversioned()
        strict_stale_rejected = _reject_strict_stale()

        if ENVIRONMENT == "local":
            if not _service_is_running(PERSISTENT_HOST):
                raise SchemaMigrationDrillError(
                    "本地 current-snapshot 验收要求已运行的 postgres 只读源"
                )
            snapshot_mode = "current_persistent_snapshot"
            snapshot_sources = {
                "primary": f"{PERSISTENT_HOST}/{PERSISTENT_PRIMARY_DATABASE}",
                "question_bank": f"{PERSISTENT_HOST}/{PERSISTENT_CATALOG_DATABASE}",
                "access": "SELECT_and_pg_dump_only",
            }
            primary_backup = _encrypted_backup_restore(
                label="current-primary-snapshot",
                source_host=PERSISTENT_HOST,
                source_database=PERSISTENT_PRIMARY_DATABASE,
                target_database=PRIMARY_RESTORE_DATABASE,
                fingerprint=_primary_fingerprint,
                source_password_secret="persistent_postgres_password",
            )
            catalog_backup = _encrypted_backup_restore(
                label="current-catalog-snapshot",
                source_host=PERSISTENT_HOST,
                source_database=PERSISTENT_CATALOG_DATABASE,
                target_database=CATALOG_RESTORE_DATABASE,
                fingerprint=_catalog_fingerprint,
                source_password_secret="persistent_postgres_password",
            )
        else:
            snapshot_mode = "deterministic_legacy_fixture_not_current_snapshot"
            snapshot_sources = {
                "primary": f"{SOURCE_HOST}/{PRIMARY_SOURCE_DATABASE}",
                "question_bank": f"{SOURCE_HOST}/{CATALOG_SOURCE_DATABASE}",
                "access": "generated_from_revision_chain",
            }
            _schema_admin(
                action="downgrade", alias="primary", host=SOURCE_HOST,
                database=PRIMARY_SOURCE_DATABASE, revision=PRIMARY_BASELINE,
                allow_destructive=True,
            )
            _schema_admin(
                action="downgrade", alias="question-bank", host=SOURCE_HOST,
                database=CATALOG_SOURCE_DATABASE, revision="catalog_0001_baseline",
                allow_destructive=True,
            )
            _psql(
                SOURCE_HOST, PRIMARY_SOURCE_DATABASE,
                "DROP TABLE alembic_version_learning;",
            )
            _psql(
                SOURCE_HOST, CATALOG_SOURCE_DATABASE,
                "DROP TABLE alembic_version_catalog;",
            )
            primary_backup = _encrypted_backup_restore(
                label="deterministic-primary-legacy-fixture",
                source_host=SOURCE_HOST,
                source_database=PRIMARY_SOURCE_DATABASE,
                target_database=PRIMARY_RESTORE_DATABASE,
                fingerprint=_primary_fingerprint,
                source_password_secret="tmpfs_postgres_password",
            )
            catalog_backup = _encrypted_backup_restore(
                label="deterministic-catalog-legacy-fixture",
                source_host=SOURCE_HOST,
                source_database=CATALOG_SOURCE_DATABASE,
                target_database=CATALOG_RESTORE_DATABASE,
                fingerprint=_catalog_fingerprint,
                source_password_secret="tmpfs_postgres_password",
            )

        if snapshot_mode == "current_persistent_snapshot":
            # 当前快照已经版本化；不得伪装成 legacy 重复 baseline adoption。
            final_primary_restore = _primary_fingerprint(
                RESTORE_HOST, PRIMARY_RESTORE_DATABASE
            )
            final_catalog_restore = _catalog_fingerprint(
                RESTORE_HOST, CATALOG_RESTORE_DATABASE
            )
            for label, backup, after in (
                ("primary", primary_backup, final_primary_restore),
                ("question-bank", catalog_backup, final_catalog_restore),
            ):
                before = backup["restored_fingerprint_before_adoption"]
                if before["content_sha256"] != after["content_sha256"]:
                    raise SchemaMigrationDrillError(f"{label} 当前版本化快照恢复后内容不一致")
                if before["table_row_counts"] != after["table_row_counts"]:
                    raise SchemaMigrationDrillError(f"{label} 当前版本化快照恢复后行数不一致")
                backup["versioned_snapshot_content_preserved"] = True
            adoption_evidence: dict[str, Any] = {
                "mode": "not_applicable_already_versioned",
                "primary_restore": final_primary_restore,
                "catalog_restore": final_catalog_restore,
            }
        else:
            # 真实 PostgreSQL 破坏一个命名索引，adoption 必须在 stamp 前拒绝。
            _psql(
                RESTORE_HOST, PRIMARY_RESTORE_DATABASE,
                "DROP INDEX idx_user_achievement_user;",
            )
            broken_contract = _schema_admin(
                action="adopt-baseline", alias="primary", host=RESTORE_HOST,
                database=PRIMARY_RESTORE_DATABASE, allow_baseline=True,
                expect_failure=True,
            )
            if "索引" not in f"{broken_contract.stdout}\n{broken_contract.stderr}":
                raise SchemaMigrationDrillError("约束破坏基线虽被拒绝，但诊断不清晰")
            if _revision(
                RESTORE_HOST, PRIMARY_RESTORE_DATABASE, "alembic_version_learning"
            ) is not None:
                raise SchemaMigrationDrillError("adoption 拒绝后不得残留 baseline stamp")
            _psql(
                RESTORE_HOST, PRIMARY_RESTORE_DATABASE,
                "CREATE INDEX idx_user_achievement_user ON user_achievements(user_id);",
            )
            for alias, database in (
                ("primary", PRIMARY_RESTORE_DATABASE),
                ("question-bank", CATALOG_RESTORE_DATABASE),
            ):
                _schema_admin(
                    action="adopt-baseline", alias=alias, host=RESTORE_HOST,
                    database=database, allow_baseline=True,
                )
            final_primary_restore = _primary_fingerprint(
                RESTORE_HOST, PRIMARY_RESTORE_DATABASE
            )
            final_catalog_restore = _catalog_fingerprint(
                RESTORE_HOST, CATALOG_RESTORE_DATABASE
            )
            for label, before, after in (
                ("primary", primary_backup["restored_fingerprint_before_adoption"], final_primary_restore),
                ("question-bank", catalog_backup["restored_fingerprint_before_adoption"], final_catalog_restore),
            ):
                if before["business_content_sha256"] != after["business_content_sha256"]:
                    raise SchemaMigrationDrillError(f"{label} adoption/upgrade 改变了受管理表行内容")
                before_counts = {k: v for k, v in before["table_row_counts"].items() if k != "admin_change_audits"}
                after_counts = {k: v for k, v in after["table_row_counts"].items() if k != "admin_change_audits"}
                if before_counts != after_counts:
                    raise SchemaMigrationDrillError(f"{label} adoption/upgrade 改变了受管理表行数")
            primary_backup["adoption_content_preserved"] = True
            catalog_backup["adoption_content_preserved"] = True
            adoption_evidence = {
                "mode": "legacy_adoption_verified",
                "primary_restore": final_primary_restore,
                "catalog_restore": final_catalog_restore,
            }
        strict_health = _start_strict_backend(
            primary_host=RESTORE_HOST,
            primary_database=PRIMARY_RESTORE_DATABASE,
            catalog_host=RESTORE_HOST,
            catalog_database=CATALOG_RESTORE_DATABASE,
        )

        report = {
            "status": "passed",
            "environment": ENVIRONMENT,
            "targets": {
                "primary_source": f"{SOURCE_HOST}/{PRIMARY_SOURCE_DATABASE}",
                "catalog_source": f"{SOURCE_HOST}/{CATALOG_SOURCE_DATABASE}",
                "primary_restore": f"{RESTORE_HOST}/{PRIMARY_RESTORE_DATABASE}",
                "catalog_restore": f"{RESTORE_HOST}/{CATALOG_RESTORE_DATABASE}",
                "verified_storage": storage_evidence,
            },
            "approved_heads": {
                "primary": PRIMARY_HEAD,
                "question_bank": CATALOG_HEAD,
            },
            "empty_database_upgrade": {
                "primary": primary_empty_head,
                "question_bank": catalog_empty_head,
            },
            "release_bootstrap": {
                "targets": {
                    "primary": f"{SOURCE_HOST}/{PRIMARY_BOOTSTRAP_DATABASE}",
                    "question_bank": f"{SOURCE_HOST}/{CATALOG_BOOTSTRAP_DATABASE}",
                    "database_name_policy": "ordinary_non_test_non_restore",
                },
                "primary_first_success": primary_first_revision,
                "primary_single_entry_repeat": True,
                "catalog_failure_after_primary_success": True,
                "catalog_single_entry_retry": {
                    "question_bank": catalog_retry_revision,
                    "primary_before": primary_before_catalog_retry,
                    "primary_after": primary_after_catalog_retry,
                    "primary_unchanged": True,
                },
                "aggregate_repeat": aggregate_repeat,
            },
            "revision_downgrade_upgrade": {
                "primary_head_to_baseline": primary_at_baseline,
                "primary_baseline_to_base": primary_at_base,
                "primary_base_to_baseline": primary_baseline_reapplied,
                "primary_baseline_to_head": primary_head_reapplied,
                "catalog_head_to_base": catalog_at_base,
                "catalog_base_to_head": catalog_head_reapplied,
            },
            "baseline_evidence": {
                "mode": snapshot_mode,
                "sources": snapshot_sources,
            },
            "restored_baseline_adoption": adoption_evidence,
            "backup_restore": {
                "primary": primary_backup,
                "question_bank": catalog_backup,
            },
            "failure_rejections": {
                "cross_database_revision": True,
                "strict_unversioned_startup": strict_unversioned_rejected,
                "strict_stale_startup": strict_stale_rejected,
                "broken_contract_before_stamp": True,
            },
            "strict_application": strict_health,
            "secret_transport": {
                "schema_adapter": "database_url_file_only",
                "compose_secret_files": True,
                "compose_config_contains_database_secret": False,
                "container_metadata_contains_database_secret": False,
                "argv_contains_database_url": False,
            },
            "elapsed_seconds": round(time.perf_counter() - started_at, 3),
            "completed_at": datetime.now(UTC).isoformat(),
        }
        report_payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        assert_no_secret_material(
            stage="Schema 演练报告",
            payload=report_payload,
            secret_values=(
                _TMPFS_DATABASE_PASSWORD,
                _database_url(SOURCE_HOST, PRIMARY_SOURCE_DATABASE),
                _database_url(SOURCE_HOST, CATALOG_SOURCE_DATABASE),
            ),
        )
        report_path = ACCEPTANCE_ROOT / "drill-report.json"
        report_path.write_text(
            report_payload,
            encoding="utf-8",
        )
        print(f"Schema 迁移演练通过，报告：{report_path}")
        return report
    finally:
        if _container_exists(BACKEND_PROBE_CONTAINER):
            _run(
                ["docker", "rm", "-f", BACKEND_PROBE_CONTAINER],
                stage="清理 strict 应用探针",
                echo=False,
            )
        _compose(
            *compose,
            "stop",
            SOURCE_HOST,
            RESTORE_HOST,
            stage="停止四目标 tmpfs PostgreSQL",
            echo=False,
        )
        for runtime_file in (
            RUNTIME_ROOT / "backup_key",
            tmpfs_password_file,
            persistent_password_file,
            primary_url_file,
            catalog_url_file,
        ):
            runtime_file.unlink(missing_ok=True)
        for key, previous_value in previous_secret_environment.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value
        _TMPFS_DATABASE_PASSWORD = None


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    try:
        run_drill()
    except SchemaMigrationDrillError as exc:
        print(f"Schema 迁移演练失败：{redact(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
