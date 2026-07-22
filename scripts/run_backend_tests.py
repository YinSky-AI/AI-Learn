"""在无持久卷的隔离 PostgreSQL 中运行后端测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import urlsplit


DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@postgres-test:5432/learning_platform_test"
)


def validate_test_database_url(url: str, environment: str) -> tuple[str, str, str]:
    """只允许明确命名的本地/CI 可丢弃数据库目标。"""

    parsed = urlsplit(url)
    host = parsed.hostname or ""
    database = parsed.path.lstrip("/")
    allowed_hosts = {"postgres-test", "localhost", "127.0.0.1"}
    disposable_name = database.endswith("_test") or database.startswith("test_")
    if host not in allowed_hosts or not disposable_name or environment not in {"local", "ci"}:
        raise ValueError("后端测试只允许 local/ci 环境中的可丢弃测试数据库")
    return host, database, environment


def _run(command: list[str]) -> int:
    return subprocess.run(command, check=False).returncode


def main() -> int:
    environment = os.getenv("DELIVERY_TEST_ENV", "local")
    database_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    try:
        host, database, verified_environment = validate_test_database_url(database_url, environment)
    except ValueError as exc:
        print(f"拒绝运行后端测试：{exc}", file=sys.stderr)
        return 2

    print(
        "隔离测试数据库目标已核验："
        f"host={host} database={database} environment={verified_environment}"
    )
    compose = ["docker", "compose", "--profile", "delivery-test"]
    if _run([*compose, "up", "-d", "--wait", "postgres-test"]):
        print("无法启动隔离 PostgreSQL 测试服务。", file=sys.stderr)
        return 1

    pytest_args = sys.argv[1:] or ["-q"]
    try:
        return _run(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "--no-deps",
                "-e",
                f"TEST_DATABASE_URL={database_url}",
                "-e",
                f"DATABASE_URL={database_url}",
                "backend",
                "pytest",
                *pytest_args,
            ]
        )
    finally:
        _run([*compose, "stop", "postgres-test"])


if __name__ == "__main__":
    raise SystemExit(main())
