"""在无持久卷的隔离 PostgreSQL 中运行后端测试。"""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = ROOT / "test" / ".runtime" / "P0-07" / "backend-tests"
sys.path.insert(0, str(ROOT / "backend"))

from app.core.schema_version import (  # noqa: E402
    SchemaVersionError,
    validate_test_database_target,
)


def validate_test_database_url(url: str, environment: str) -> tuple[str, str, str]:
    """保持脚本 API，同时复用后端连接前的统一安全边界。"""

    try:
        return validate_test_database_target(url, environment)
    except SchemaVersionError as exc:
        raise ValueError(str(exc)) from exc


def _run(command: list[str], *, environment: dict[str, str]) -> int:
    return subprocess.run(command, check=False, env=environment).returncode


def _schema_command(
    *, action: str, target: str, database: str, database_url_file: str, environment: str
) -> list[str]:
    return [
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
        target,
        "--database-url-file",
        database_url_file,
        "--environment",
        environment,
        "--expected-host",
        "postgres-test",
        "--expected-database",
        database,
    ]


def main() -> int:
    environment = os.getenv("DELIVERY_TEST_ENV", "local")
    database = "learning_platform_test"
    question_database = "ai_learn_test"
    password = secrets.token_urlsafe(24)
    encoded_password = quote(password, safe="")
    database_url = (
        f"postgresql+asyncpg://postgres:{encoded_password}@postgres-test:5432/{database}"
    )
    question_database_url = (
        "postgresql+asyncpg://postgres:"
        f"{encoded_password}@postgres-test:5432/{question_database}"
    )
    try:
        host, database, verified_environment = validate_test_database_url(
            database_url, environment
        )
    except ValueError as exc:
        print(f"拒绝运行后端测试：{exc}", file=sys.stderr)
        return 2

    print(
        "隔离测试数据库目标已核验："
        f"host={host} database={database} environment={verified_environment}"
    )
    compose = ["docker", "compose", "--profile", "delivery-test"]
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    password_file = RUNTIME_ROOT / "postgres_password"
    primary_url_file = RUNTIME_ROOT / "primary_database_url"
    catalog_url_file = RUNTIME_ROOT / "catalog_database_url"
    password_file.write_text(password + "\n", encoding="utf-8")
    primary_url_file.write_text(database_url + "\n", encoding="utf-8")
    catalog_url_file.write_text(question_database_url + "\n", encoding="utf-8")
    subprocess_environment = {
        **os.environ,
        "POSTGRES_PASSWORD_SECRET_FILE": str(password_file.resolve()),
        "PRIMARY_DATABASE_URL_SECRET_FILE": str(primary_url_file.resolve()),
        "CATALOG_DATABASE_URL_SECRET_FILE": str(catalog_url_file.resolve()),
    }
    try:
        if _run(
            [*compose, "up", "-d", "--force-recreate", "--wait", "postgres-test"],
            environment=subprocess_environment,
        ):
            print("无法启动隔离 PostgreSQL 测试服务。", file=sys.stderr)
            return 1

        if _run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres-test",
                "createdb",
                "--username",
                "postgres",
                question_database,
            ],
            environment=subprocess_environment,
        ):
            print("无法创建隔离题库测试数据库。", file=sys.stderr)
            return 1
        for target, target_database, target_url_file in (
            ("primary", database, "/run/secrets/primary_database_url"),
            ("question-bank", question_database, "/run/secrets/catalog_database_url"),
        ):
            if _run(
                _schema_command(
                    action="upgrade",
                    target=target,
                    database=target_database,
                    database_url_file=target_url_file,
                    environment=environment,
                ),
                environment=subprocess_environment,
            ) or _run(
                _schema_command(
                    action="check",
                    target=target,
                    database=target_database,
                    database_url_file=target_url_file,
                    environment=environment,
                ),
                environment=subprocess_environment,
            ):
                print("隔离测试库迁移或 Alembic drift 检查失败。", file=sys.stderr)
                return 1

        pytest_args = sys.argv[1:] or ["-q"]
        return _run(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "--no-deps",
                "-e",
                "TEST_DATABASE_URL_FILE=/run/secrets/primary_database_url",
                "-e",
                "SCHEMA_VERSION_POLICY=strict",
                "backend",
                "pytest",
                *pytest_args,
            ],
            environment=subprocess_environment,
        )
    finally:
        _run(
            [*compose, "stop", "postgres-test"],
            environment=subprocess_environment,
        )
        for runtime_file in (password_file, primary_url_file, catalog_url_file):
            runtime_file.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
