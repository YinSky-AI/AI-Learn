"""PostgreSQL 加密备份、校验、隔离恢复与保留计划工具。"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Iterable


MAGIC = b"AILEARN_BACKUP_V1\n"
NONCE_SIZE = 12
TAG_SIZE = 16
CHUNK_SIZE = 1024 * 1024
SAFE_RESTORE_SUFFIXES = ("_restore", "_recovery", "_test")
NON_PRODUCTION_ENVIRONMENTS = {"local", "ci", "test"}
KNOWN_ENVIRONMENTS = NON_PRODUCTION_ENVIRONMENTS | {"staging", "production"}
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class BackupRecoveryError(RuntimeError):
    """可安全直接显示给运维执行者的失败。"""


def redact(value: str) -> str:
    """从外部命令诊断中移除连接凭据、密码和令牌。"""

    value = re.sub(
        r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^\s:/@]+):[^\s@]+@",
        r"\g<scheme>\g<user>:***@",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"(?i)(password\s*[=:]\s*)[^\s]+", r"\1***", value)
    return re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]+", r"\1***", value)


def _validate_target_fields(host: str, database: str, environment: str) -> None:
    if not host or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", host):
        raise BackupRecoveryError("数据库 host 为空或格式不安全")
    if not database or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,62}", database):
        raise BackupRecoveryError("数据库名称为空或格式不安全")
    if environment not in KNOWN_ENVIRONMENTS:
        raise BackupRecoveryError("environment 必须是 local、ci、test、staging 或 production")


def validate_backup_target(
    *, host: str, database: str, environment: str, allow_production: bool
) -> None:
    """核验只读备份源；生产源必须显式确认。"""

    _validate_target_fields(host, database, environment)
    if environment == "production" and not allow_production:
        raise BackupRecoveryError("生产源备份必须明确确认并提供已批准的变更窗口")


def validate_restore_target(
    *,
    source_host: str,
    source_database: str,
    target_host: str,
    target_database: str,
    target_environment: str,
) -> None:
    """保证恢复目标是与源分离的非生产可丢弃数据库。"""

    _validate_target_fields(source_host, source_database, target_environment)
    _validate_target_fields(target_host, target_database, target_environment)
    if (source_host, source_database) == (target_host, target_database):
        raise BackupRecoveryError("恢复目标不能是源数据库")
    if target_environment not in NON_PRODUCTION_ENVIRONMENTS:
        raise BackupRecoveryError("恢复只允许非生产环境；生产恢复由独立审批流程执行")
    if not target_database.endswith(SAFE_RESTORE_SUFFIXES):
        raise BackupRecoveryError("恢复目标数据库必须是可丢弃恢复库（_restore/_recovery/_test）")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_checksum(path: Path, expected: str) -> None:
    """验证产物 SHA-256；失败时阻止解密和恢复。"""

    if not path.is_file():
        raise BackupRecoveryError(f"备份产物不存在：{path.name}")
    if not SHA256_PATTERN.fullmatch(expected) or _sha256(path) != expected:
        raise BackupRecoveryError("备份校验和不匹配，已停止后续操作")


def validate_manifest(manifest: dict[str, Any]) -> None:
    """验证备份清单的安全关键字段。"""

    if manifest.get("format_version") != 1:
        raise BackupRecoveryError("备份清单版本不受支持")
    if manifest.get("encryption") != "AES-256-GCM":
        raise BackupRecoveryError("备份清单必须使用 AES-256-GCM 认证加密")
    if not SHA256_PATTERN.fullmatch(str(manifest.get("sha256", ""))):
        raise BackupRecoveryError("备份清单缺少有效 SHA-256")
    replica = manifest.get("replica")
    if not isinstance(replica, dict) or replica.get("status") != "verified" or not replica.get("domain"):
        raise BackupRecoveryError("备份清单缺少已校验的副本域")


def plan_retention(
    files: Iterable[Path], *, keep_days: int, now: datetime | None = None
) -> list[Path]:
    """仅生成过期候选清单；本工具不删除任何备份。"""

    if keep_days < 1:
        raise BackupRecoveryError("保留天数必须大于 0")
    reference = now or datetime.now(UTC)
    cutoff = reference - timedelta(days=keep_days)
    return sorted(
        path
        for path in files
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff
    )


def _read_password(path: Path, label: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise BackupRecoveryError(f"无法读取{label}密码文件") from exc
    if not value:
        raise BackupRecoveryError(f"{label}密码文件为空")
    return value


def _read_key(path: Path) -> bytes:
    try:
        key = path.read_bytes()
    except OSError as exc:
        raise BackupRecoveryError("无法读取备份加密密钥文件") from exc
    if len(key) != 32:
        raise BackupRecoveryError("备份加密密钥必须恰好为 32 字节")
    return key


def _run(command: list[str], *, stage: str, password: str | None = None) -> str:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    if password is not None:
        environment["PGPASSWORD"] = password
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    if result.returncode:
        detail = redact((result.stderr or result.stdout).strip())
        if len(detail) > 800:
            detail = detail[-800:]
        raise BackupRecoveryError(f"{stage}失败：{detail or '外部命令未提供诊断'}")
    return result.stdout.strip()


def _encrypt_archive(source: Path, destination: Path, key: bytes) -> None:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    nonce = os.urandom(NONCE_SIZE)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    partial = destination.with_suffix(destination.suffix + ".partial")
    try:
        with source.open("rb") as source_stream, partial.open("wb") as target_stream:
            target_stream.write(MAGIC)
            target_stream.write(nonce)
            for chunk in iter(lambda: source_stream.read(CHUNK_SIZE), b""):
                target_stream.write(encryptor.update(chunk))
            target_stream.write(encryptor.finalize())
            target_stream.write(encryptor.tag)
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def _decrypt_archive(source: Path, destination: Path, key: bytes) -> None:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.exceptions import InvalidTag

    size = source.stat().st_size
    minimum_size = len(MAGIC) + NONCE_SIZE + TAG_SIZE + 1
    if size < minimum_size:
        raise BackupRecoveryError("加密备份格式无效或已截断")
    with source.open("rb") as source_stream:
        if source_stream.read(len(MAGIC)) != MAGIC:
            raise BackupRecoveryError("加密备份魔数无效")
        nonce = source_stream.read(NONCE_SIZE)
        ciphertext_size = size - len(MAGIC) - NONCE_SIZE - TAG_SIZE
        source_stream.seek(size - TAG_SIZE)
        tag = source_stream.read(TAG_SIZE)
        source_stream.seek(len(MAGIC) + NONCE_SIZE)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        remaining = ciphertext_size
        try:
            with destination.open("wb") as target_stream:
                while remaining:
                    chunk = source_stream.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise BackupRecoveryError("加密备份读取不完整")
                    remaining -= len(chunk)
                    target_stream.write(decryptor.update(chunk))
                target_stream.write(decryptor.finalize())
        except InvalidTag as exc:
            destination.unlink(missing_ok=True)
            raise BackupRecoveryError("备份认证标签无效，密钥错误或产物已被篡改") from exc


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    try:
        partial.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupRecoveryError("无法读取有效备份清单") from exc
    if not isinstance(payload, dict):
        raise BackupRecoveryError("备份清单必须是对象")
    validate_manifest(payload)
    return payload


def _assert_target_empty(host: str, database: str, password: str) -> None:
    output = _run(
        [
            "psql",
            "--no-password",
            "--tuples-only",
            "--no-align",
            "--host",
            host,
            "--username",
            "postgres",
            "--dbname",
            database,
            "--command",
            (
                "SELECT COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
                "AND c.relkind IN ('r','p','v','m','S');"
            ),
        ],
        stage="恢复目标空库检查",
        password=password,
    )
    if output.strip() != "0":
        raise BackupRecoveryError("恢复目标不是空库，拒绝覆盖已有 Schema 或数据")


def _replica_is_independent(primary: Path, replica: Path) -> bool:
    try:
        return primary.stat().st_dev != replica.stat().st_dev
    except OSError as exc:
        raise BackupRecoveryError("无法核验主备份与副本的存储设备") from exc


def command_backup(args: argparse.Namespace) -> None:
    validate_backup_target(
        host=args.source_host,
        database=args.source_database,
        environment=args.environment,
        allow_production=args.allow_production_source_backup,
    )
    primary_dir = args.backup_dir.resolve()
    replica_dir = args.replica_dir.resolve()
    if primary_dir == replica_dir:
        raise BackupRecoveryError("主备份目录与副本目录必须不同")
    primary_dir.mkdir(parents=True, exist_ok=True)
    replica_dir.mkdir(parents=True, exist_ok=True)
    independent_device = _replica_is_independent(primary_dir, replica_dir)
    if not independent_device and (
        args.environment == "production" or not args.allow_same_device_rehearsal
    ):
        raise BackupRecoveryError("副本不在独立存储设备；仅本地演练可显式放宽")

    password = _read_password(args.source_password_file, "源数据库")
    key = _read_key(args.key_file)
    backup_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    stem = f"{args.source_database}-{backup_id}"
    archive = primary_dir / f"{stem}.aibak"
    manifest_path = primary_dir / f"{stem}.manifest.json"
    checksum_path = primary_dir / f"{stem}.sha256"
    if any(path.exists() for path in (archive, manifest_path, checksum_path)):
        raise BackupRecoveryError("备份目标文件已存在，拒绝覆盖")

    started_at = datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix="ai-learn-backup-") as temp_dir:
        raw_archive = Path(temp_dir) / "database.dump"
        _run(
            [
                "pg_dump",
                "--host",
                args.source_host,
                "--username",
                "postgres",
                "--dbname",
                args.source_database,
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--file",
                str(raw_archive),
            ],
            stage="pg_dump",
            password=password,
        )
        _run(["pg_restore", "--list", str(raw_archive)], stage="备份归档结构检查")
        _encrypt_archive(raw_archive, archive, key)

    checksum = _sha256(archive)
    replica_archive = replica_dir / archive.name
    if replica_archive.exists():
        raise BackupRecoveryError("副本目标文件已存在，拒绝覆盖")
    shutil.copy2(archive, replica_archive)
    verify_file_checksum(replica_archive, checksum)
    duration_seconds = round((datetime.now(UTC) - started_at).total_seconds(), 3)
    manifest = {
        "format_version": 1,
        "backup_id": backup_id,
        "created_at": started_at.isoformat(),
        "source": {
            "host": args.source_host,
            "database": args.source_database,
            "environment": args.environment,
        },
        "archive": archive.name,
        "archive_size_bytes": archive.stat().st_size,
        "encryption": "AES-256-GCM",
        "sha256": checksum,
        "pg_dump_version": _run(["pg_dump", "--version"], stage="pg_dump 版本检查"),
        "duration_seconds": duration_seconds,
        "rpo_target_minutes": args.rpo_minutes,
        "rto_target_minutes": args.rto_minutes,
        "replica": {
            "status": "verified",
            "domain": args.replica_domain,
            "independent_device": independent_device,
            "rehearsal_only": not independent_device,
        },
    }
    validate_manifest(manifest)
    _write_json_atomic(manifest_path, manifest)
    checksum_path.write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    shutil.copy2(manifest_path, replica_dir / manifest_path.name)
    shutil.copy2(checksum_path, replica_dir / checksum_path.name)

    print(
        "备份目标已核验："
        f"host={args.source_host} database={args.source_database} environment={args.environment}"
    )
    print(f"加密备份完成：{archive.name}，耗时 {duration_seconds:.3f} 秒")
    print(f"SHA-256：{checksum}")
    print(
        "副本校验完成："
        f"domain={args.replica_domain} independent_device={str(independent_device).lower()}"
    )
    print(f"清单：{manifest_path}")


def command_verify(args: argparse.Namespace) -> None:
    manifest = _load_manifest(args.manifest)
    verify_file_checksum(args.archive, str(manifest["sha256"]))
    key = _read_key(args.key_file)
    with tempfile.TemporaryDirectory(prefix="ai-learn-verify-") as temp_dir:
        raw_archive = Path(temp_dir) / "database.dump"
        _decrypt_archive(args.archive, raw_archive, key)
        entries = _run(["pg_restore", "--list", str(raw_archive)], stage="备份归档结构检查")
        if not entries:
            raise BackupRecoveryError("备份归档没有可恢复对象")
    print(f"备份校验通过：{args.archive.name}")


def command_restore(args: argparse.Namespace) -> None:
    manifest = _load_manifest(args.manifest)
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise BackupRecoveryError("备份清单缺少源数据库目标")
    validate_restore_target(
        source_host=str(source.get("host", "")),
        source_database=str(source.get("database", "")),
        target_host=args.target_host,
        target_database=args.target_database,
        target_environment=args.target_environment,
    )
    verify_file_checksum(args.archive, str(manifest["sha256"]))
    password = _read_password(args.target_password_file, "恢复目标")
    key = _read_key(args.key_file)
    _assert_target_empty(args.target_host, args.target_database, password)
    started_at = datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix="ai-learn-restore-") as temp_dir:
        raw_archive = Path(temp_dir) / "database.dump"
        _decrypt_archive(args.archive, raw_archive, key)
        _run(["pg_restore", "--list", str(raw_archive)], stage="恢复前归档结构检查")
        _run(
            [
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "--host",
                args.target_host,
                "--username",
                "postgres",
                "--dbname",
                args.target_database,
                str(raw_archive),
            ],
            stage="pg_restore",
            password=password,
        )
    duration_seconds = round((datetime.now(UTC) - started_at).total_seconds(), 3)
    print(
        "恢复目标已核验："
        f"host={args.target_host} database={args.target_database} "
        f"environment={args.target_environment}"
    )
    print(f"隔离恢复完成，耗时 {duration_seconds:.3f} 秒")


def command_retention_plan(args: argparse.Namespace) -> None:
    candidates = plan_retention(
        args.backup_dir.glob("*.aibak"),
        keep_days=args.keep_days,
    )
    print(f"保留策略 dry-run：{len(candidates)} 个候选；未删除任何文件。")
    for candidate in candidates:
        print(candidate.name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI-Learn PostgreSQL 加密备份与隔离恢复")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="创建加密备份并校验副本")
    backup.add_argument("--source-host", required=True)
    backup.add_argument("--source-database", required=True)
    backup.add_argument("--environment", required=True)
    backup.add_argument("--source-password-file", type=Path, required=True)
    backup.add_argument("--key-file", type=Path, required=True)
    backup.add_argument("--backup-dir", type=Path, required=True)
    backup.add_argument("--replica-dir", type=Path, required=True)
    backup.add_argument("--replica-domain", required=True)
    backup.add_argument("--rpo-minutes", type=int, default=1440)
    backup.add_argument("--rto-minutes", type=int, default=30)
    backup.add_argument("--allow-production-source-backup", action="store_true")
    backup.add_argument("--allow-same-device-rehearsal", action="store_true")
    backup.set_defaults(handler=command_backup)

    verify = subparsers.add_parser("verify", help="校验、解密并检查备份归档")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--key-file", type=Path, required=True)
    verify.set_defaults(handler=command_verify)

    restore = subparsers.add_parser("restore", help="恢复到已核验的空白可丢弃数据库")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--manifest", type=Path, required=True)
    restore.add_argument("--key-file", type=Path, required=True)
    restore.add_argument("--target-host", required=True)
    restore.add_argument("--target-database", required=True)
    restore.add_argument("--target-environment", required=True)
    restore.add_argument("--target-password-file", type=Path, required=True)
    restore.set_defaults(handler=command_restore)

    retention = subparsers.add_parser("retention-plan", help="仅列出过期候选，不删除")
    retention.add_argument("--backup-dir", type=Path, required=True)
    retention.add_argument("--keep-days", type=int, default=35)
    retention.set_defaults(handler=command_retention_plan)
    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except BackupRecoveryError as exc:
        print(f"备份恢复失败：{redact(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
