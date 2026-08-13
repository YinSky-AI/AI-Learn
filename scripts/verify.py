"""AI-Learn 本地与 CI 共用的跨平台交付验证编排器。"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from typing import Iterator, Mapping
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
FULL_GATE_RUNTIME_ROOT = ROOT / "test" / ".runtime" / "delivery-full"


@dataclass(frozen=True)
class Step:
    label: str
    command: tuple[str, ...]
    cwd: Path = ROOT
    environment: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class FullGateSecretFiles:
    """完整门禁创建并最终清理的 file-only 运行时 secret。"""

    runtime_root: Path
    password_file: Path
    primary_database_url_file: Path
    catalog_database_url_file: Path

    def environment(self) -> dict[str, str]:
        return {
            "DELIVERY_TEST_ENV": "ci",
            "POSTGRES_PASSWORD_SECRET_FILE": str(self.password_file.resolve()),
            "PRIMARY_DATABASE_URL_SECRET_FILE": str(
                self.primary_database_url_file.resolve()
            ),
            "CATALOG_DATABASE_URL_SECRET_FILE": str(
                self.catalog_database_url_file.resolve()
            ),
        }

    def cleanup(self) -> None:
        for secret_file in (
            self.password_file,
            self.primary_database_url_file,
            self.catalog_database_url_file,
        ):
            try:
                secret_file.chmod(0o600)
            except OSError:
                pass
            secret_file.unlink(missing_ok=True)
        for directory in (self.password_file.parent, self.runtime_root):
            try:
                directory.rmdir()
            except OSError:
                # 只删除本次创建的已知文件；不触碰并存的其他运行时证据。
                pass


def _write_runtime_secret(path: Path, value: str) -> None:
    path.write_text(value + "\n", encoding="utf-8", newline="\n")
    if path.read_bytes().startswith(b"\xef\xbb\xbf"):
        raise RuntimeError("运行时 secret 禁止包含 UTF-8 BOM")
    try:
        path.chmod(0o444)
    except OSError:
        # Windows ACL 由当前用户目录继承；容器只读挂载仍是强制边界。
        pass


def _load_external_secret(path_value: str, label: str) -> tuple[Path, str]:
    path = Path(path_value)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError(f"{label} 必须是绝对路径普通文件")
    try:
        if not path.is_file() or path.stat().st_size > 4096:
            raise ValueError(f"{label} 文件无效")
        raw_value = path.read_text(encoding="utf-8")
    except ValueError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"{label} 文件不可读") from exc
    if raw_value.startswith("\ufeff"):
        raise ValueError(f"{label} 禁止包含 UTF-8 BOM")
    lines = raw_value.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise ValueError(f"{label} 必须是非空单行文件")
    return path, lines[0].strip()


def validated_external_full_gate_environment(
    source: Mapping[str, str],
) -> dict[str, str] | None:
    """三个外部 secret all-or-none，并核验 DSN 与密码属于当前 Compose 双库。"""

    keys = (
        "POSTGRES_PASSWORD_SECRET_FILE",
        "PRIMARY_DATABASE_URL_SECRET_FILE",
        "CATALOG_DATABASE_URL_SECRET_FILE",
    )
    present = [key for key in keys if source.get(key)]
    if present and len(present) != len(keys):
        raise ValueError("full gate 外部 secret 必须同时提供密码、主库 DSN 和题库 DSN 文件")
    if not present:
        return None
    password_path, password = _load_external_secret(source[keys[0]], "PostgreSQL 密码 secret")
    primary_path, primary_url = _load_external_secret(source[keys[1]], "主库 DSN secret")
    catalog_path, catalog_url = _load_external_secret(source[keys[2]], "题库 DSN secret")
    for label, database_url, expected_database in (
        ("主库", primary_url, "learning_platform"),
        ("题库", catalog_url, "ai_learn"),
    ):
        parsed = urlsplit(database_url)
        if (
            parsed.scheme != "postgresql+asyncpg"
            or parsed.username != "postgres"
            or parsed.hostname != "postgres"
            or parsed.path.lstrip("/") != expected_database
            or unquote(parsed.password or "") != password
        ):
            raise ValueError(f"{label} DSN secret 与 Compose 目标或密码不一致")
    return {
        "DELIVERY_TEST_ENV": "ci",
        keys[0]: str(password_path.resolve()),
        keys[1]: str(primary_path.resolve()),
        keys[2]: str(catalog_path.resolve()),
    }


def prepare_full_gate_secrets(
    runtime_root: Path = FULL_GATE_RUNTIME_ROOT,
) -> FullGateSecretFiles:
    """为 clean full gate 创建不进入 argv/日志的随机 file-only secrets。"""

    secret_root = runtime_root / "secrets"
    secret_root.mkdir(parents=True, exist_ok=True)
    try:
        secret_root.chmod(0o700)
    except OSError:
        pass
    files = FullGateSecretFiles(
        runtime_root=runtime_root,
        password_file=secret_root / "postgres_password",
        primary_database_url_file=secret_root / "primary_database_url",
        catalog_database_url_file=secret_root / "catalog_database_url",
    )
    password = secrets.token_urlsafe(32)
    encoded_password = quote(password, safe="")
    try:
        _write_runtime_secret(files.password_file, password)
        _write_runtime_secret(
            files.primary_database_url_file,
            "postgresql+asyncpg://postgres:"
            f"{encoded_password}@postgres:5432/learning_platform",
        )
        _write_runtime_secret(
            files.catalog_database_url_file,
            "postgresql+asyncpg://postgres:"
            f"{encoded_password}@postgres:5432/ai_learn",
        )
    except Exception:
        files.cleanup()
        raise
    return files


@contextmanager
def managed_full_gate_environment(
    runtime_root: Path = FULL_GATE_RUNTIME_ROOT,
    source_environment: Mapping[str, str] | None = None,
) -> Iterator[dict[str, str]]:
    """统一管理 full gate 所有子步骤共享的 secret 文件生命周期。"""

    external = validated_external_full_gate_environment(
        os.environ if source_environment is None else source_environment
    )
    if external is not None:
        yield external
        return
    files = prepare_full_gate_secrets(runtime_root)
    try:
        yield files.environment()
    finally:
        files.cleanup()


def build_steps(mode: str) -> list[Step]:
    """返回确定、有序且遇错即停的验证步骤。"""

    steps = [
        Step(
            "交付脚本单元测试",
            (
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/tests",
                "-p",
                "test_*.py",
                "-v",
            ),
        ),
        Step(
            "方程诊断规则评测",
            (
                sys.executable,
                "-m",
                "evals.equation_diagnosis.runner",
                "--mode",
                "rules",
                "--output",
                "../test/acceptance/adaptive-learning/rules.json",
            ),
            ROOT / "backend",
        ),
        Step("前端测试", ("npm", "test"), ROOT / "frontend"),
        Step("前端类型检查", ("npm", "run", "typecheck"), ROOT / "frontend"),
        Step("前端生产构建", ("npm", "run", "build"), ROOT / "frontend"),
    ]
    if mode == "fast":
        return steps
    if mode != "full":
        raise ValueError(f"未知验证模式：{mode}")
    return [
        *steps,
        Step("后端镜像构建", ("docker", "compose", "build", "backend")),
        Step("隔离后端测试", (sys.executable, "scripts/run_backend_tests.py")),
        Step("加密备份与隔离恢复演练", (sys.executable, "scripts/run_backup_restore_drill.py")),
        Step("双数据库 Schema 迁移演练", (sys.executable, "scripts/run_schema_migration_drill.py")),
        Step(
            "Compose 依赖服务启动",
            ("docker", "compose", "up", "-d", "--wait", "postgres", "redis"),
        ),
        Step(
            "Compose 主业务库 bootstrap",
            (
                "docker", "compose", "--profile", "schema-bootstrap", "run",
                "--build", "--rm", "--no-deps", "-e",
                "SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE=CI-FULL-GATE",
                "schema-bootstrap-primary",
            ),
        ),
        Step(
            "Compose 题库 bootstrap",
            (
                "docker", "compose", "--profile", "schema-bootstrap", "run",
                "--build", "--rm", "--no-deps", "-e",
                "SCHEMA_BOOTSTRAP_APPROVAL_REFERENCE=CI-FULL-GATE",
                "schema-bootstrap-catalog",
            ),
        ),
        Step(
            "Compose 构建与启动",
            ("docker", "compose", "up", "-d", "--build", "--wait"),
            environment=(("SCHEMA_VERSION_POLICY", "strict"),),
        ),
        Step("Docker smoke", (sys.executable, "scripts/verify_delivery.py")),
        Step("真实浏览器 E2E", ("npm", "run", "e2e"), ROOT / "frontend"),
    ]


def _resolve_command(command: tuple[str, ...]) -> list[str]:
    executable = shutil.which(command[0])
    if not executable:
        raise FileNotFoundError(f"缺少验证依赖命令：{command[0]}")
    return [executable, *command[1:]]


def build_subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """确保 Python 子进程在 Windows 与 CI 上都输出 UTF-8。"""

    environment = dict(os.environ if base is None else base)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    return environment


def run(mode: str) -> int:
    steps = build_steps(mode)
    secret_context = (
        managed_full_gate_environment() if mode == "full" else nullcontext({})
    )
    with secret_context as secret_environment:
        for index, step in enumerate(steps, start=1):
            print(f"[{index}/{len(steps)}] {step.label}", flush=True)
            try:
                command = _resolve_command(step.command)
            except FileNotFoundError as exc:
                print(f"交付验证失败：{exc}", file=sys.stderr)
                return 2
            environment = build_subprocess_env()
            environment.update(secret_environment)
            environment.update(step.environment)
            result = subprocess.run(
                command,
                cwd=step.cwd,
                check=False,
                env=environment,
            )
            if result.returncode:
                print(
                    f"交付验证失败：{step.label} 返回退出码 {result.returncode}",
                    file=sys.stderr,
                )
                return result.returncode
    print(f"{mode} 交付验证全部通过。")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="运行 AI-Learn 可复现交付验证")
    parser.add_argument("mode", choices=("fast", "full"))
    return run(parser.parse_args().mode)


if __name__ == "__main__":
    raise SystemExit(main())
