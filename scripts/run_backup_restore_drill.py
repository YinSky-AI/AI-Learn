"""在固定的可丢弃 PostgreSQL 容器中运行真实加密备份与恢复演练。"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
ACCEPTANCE_ROOT = ROOT / "test" / "acceptance" / "P0-04"
RUNTIME_ROOT = ROOT / "test" / ".runtime" / "P0-04"
SOURCE_HOST = "postgres-test"
SOURCE_DATABASE = "learning_platform_test"
TARGET_HOST = "postgres-restore"
TARGET_DATABASE = "learning_platform_restore"
ENVIRONMENT = os.getenv("DELIVERY_TEST_ENV", "local")

PROBE_SCHEMA = """
CREATE TABLE public.recovery_probe (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    marker TEXT NOT NULL UNIQUE
);
INSERT INTO public.recovery_probe (marker)
VALUES ('synthetic-alpha'), ('synthetic-beta');
"""

PROBE_QUERY = """
SELECT
    COUNT(*)::text || '|' ||
    COUNT(DISTINCT marker)::text || '|' ||
    (SELECT COUNT(*) FROM pg_constraint
     WHERE conrelid = 'public.recovery_probe'::regclass
       AND contype IN ('p', 'u'))::text
FROM public.recovery_probe;
"""


class BackupDrillError(RuntimeError):
    """可直接显示给执行者的恢复演练失败。"""


def redact(value: str) -> str:
    value = re.sub(
        r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^\s:/@]+):[^\s@]+@",
        r"\g<scheme>\g<user>:***@",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"(?i)(password\s*[=:]\s*)[^\s]+", r"\1***", value)


def validate_drill_targets(
    *,
    source_host: str,
    source_database: str,
    target_host: str,
    target_database: str,
    environment: str,
) -> None:
    expected_targets = (
        SOURCE_HOST,
        SOURCE_DATABASE,
        TARGET_HOST,
        TARGET_DATABASE,
    )
    actual_targets = (source_host, source_database, target_host, target_database)
    if actual_targets != expected_targets or environment not in {"local", "ci"}:
        raise BackupDrillError("恢复演练只允许固定可丢弃目标 postgres-test → postgres-restore")


def parse_probe_fingerprint(value: str) -> dict[str, int]:
    try:
        row_count, unique_markers, constraints = (int(part) for part in value.strip().split("|"))
    except (TypeError, ValueError) as exc:
        raise BackupDrillError("恢复指纹格式无效") from exc
    fingerprint = {
        "row_count": row_count,
        "unique_markers": unique_markers,
        "constraints": constraints,
    }
    if fingerprint != {"row_count": 2, "unique_markers": 2, "constraints": 2}:
        raise BackupDrillError("恢复指纹不匹配，行数、唯一值或约束缺失")
    return fingerprint


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
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if expect_failure:
        if result.returncode == 0:
            raise BackupDrillError(f"{stage}本应拒绝执行但返回成功")
        if echo and output:
            print(redact(output))
        return result
    if result.returncode:
        detail = redact(output)
        if len(detail) > 1200:
            detail = detail[-1200:]
        raise BackupDrillError(f"{stage}失败：{detail or '命令未提供诊断'}")
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
        stage=f"{service} 数据库查询",
        input_text=sql,
        echo=echo,
    )
    return result.stdout.strip()


def _tool_command(runtime_dir: Path, *arguments: str) -> list[str]:
    runtime_mount = f"{runtime_dir.resolve().as_posix()}:/run/secrets:ro"
    evidence_mount = f"{ACCEPTANCE_ROOT.resolve().as_posix()}:/evidence"
    return [
        "docker",
        "compose",
        "--profile",
        "delivery-test",
        "run",
        "--rm",
        "--no-deps",
        "--volume",
        runtime_mount,
        "--volume",
        evidence_mount,
        "backup-tool",
        *arguments,
    ]


def _load_new_manifest(before: set[Path]) -> tuple[Path, dict[str, Any]]:
    after = set((ACCEPTANCE_ROOT / "backups" / "primary").glob("*.manifest.json"))
    created = sorted(after - before)
    if len(created) != 1:
        raise BackupDrillError(f"期望产生 1 个新备份清单，实际为 {len(created)} 个")
    try:
        manifest = json.loads(created[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupDrillError("无法读取演练生成的备份清单") from exc
    if not isinstance(manifest, dict):
        raise BackupDrillError("演练备份清单格式无效")
    return created[0], manifest


def run_drill() -> dict[str, Any]:
    validate_drill_targets(
        source_host=SOURCE_HOST,
        source_database=SOURCE_DATABASE,
        target_host=TARGET_HOST,
        target_database=TARGET_DATABASE,
        environment=ENVIRONMENT,
    )
    print(
        "恢复演练目标已二次核验："
        f"source_host={SOURCE_HOST} source_database={SOURCE_DATABASE} "
        f"target_host={TARGET_HOST} target_database={TARGET_DATABASE} "
        f"environment={ENVIRONMENT}"
    )

    primary_dir = ACCEPTANCE_ROOT / "backups" / "primary"
    replica_dir = ACCEPTANCE_ROOT / "backups" / "replica"
    logs_dir = ACCEPTANCE_ROOT / "logs"
    for directory in (primary_dir, replica_dir, logs_dir, RUNTIME_ROOT):
        directory.mkdir(parents=True, exist_ok=True)
    key_file = RUNTIME_ROOT / "backup_key"
    password_file = RUNTIME_ROOT / "postgres_password"
    corrupted_archive = RUNTIME_ROOT / "corrupted.aibak"
    key_file.write_bytes(secrets.token_bytes(32))
    password_file.write_text("postgres\n", encoding="utf-8")
    before_manifests = set(primary_dir.glob("*.manifest.json"))
    compose = ["--profile", "delivery-test"]

    try:
        _compose(*compose, "build", "backup-tool", stage="备份工具镜像构建")
        _compose(
            *compose,
            "up",
            "-d",
            "--force-recreate",
            "--wait",
            SOURCE_HOST,
            TARGET_HOST,
            stage="隔离源库和恢复库启动",
        )
        _psql(SOURCE_HOST, SOURCE_DATABASE, PROBE_SCHEMA, echo=True)
        source_before = parse_probe_fingerprint(
            _psql(SOURCE_HOST, SOURCE_DATABASE, PROBE_QUERY)
        )

        _run(
            _tool_command(
                RUNTIME_ROOT,
                "backup",
                "--source-host",
                SOURCE_HOST,
                "--source-database",
                SOURCE_DATABASE,
                "--environment",
                ENVIRONMENT,
                "--source-password-file",
                "/run/secrets/postgres_password",
                "--key-file",
                "/run/secrets/backup_key",
                "--backup-dir",
                "/evidence/backups/primary",
                "--replica-dir",
                "/evidence/backups/replica",
                "--replica-domain",
                "local-rehearsal-copy",
                "--rpo-minutes",
                "1440",
                "--rto-minutes",
                "30",
                "--allow-same-device-rehearsal",
            ),
            stage="真实 pg_dump 与加密副本",
        )
        manifest_path, manifest = _load_new_manifest(before_manifests)
        archive_name = str(manifest.get("archive", ""))
        archive_path = primary_dir / archive_name
        if not archive_name or not archive_path.is_file():
            raise BackupDrillError("备份清单引用的加密归档不存在")
        container_archive = f"/evidence/backups/primary/{archive_name}"
        container_manifest = f"/evidence/backups/primary/{manifest_path.name}"

        _run(
            _tool_command(
                RUNTIME_ROOT,
                "verify",
                "--archive",
                container_archive,
                "--manifest",
                container_manifest,
                "--key-file",
                "/run/secrets/backup_key",
            ),
            stage="加密备份解密与归档检查",
        )

        shutil.copy2(archive_path, corrupted_archive)
        with corrupted_archive.open("r+b") as stream:
            stream.seek(max(32, corrupted_archive.stat().st_size // 2))
            current = stream.read(1)
            if not current:
                raise BackupDrillError("无法构造损坏校验和演练产物")
            stream.seek(-1, 1)
            stream.write(bytes([current[0] ^ 0x01]))
        checksum_rejection = _run(
            _tool_command(
                RUNTIME_ROOT,
                "verify",
                "--archive",
                "/run/secrets/corrupted.aibak",
                "--manifest",
                container_manifest,
                "--key-file",
                "/run/secrets/backup_key",
            ),
            stage="损坏校验和拒绝演练",
            expect_failure=True,
        )
        if "校验和" not in f"{checksum_rejection.stdout}\n{checksum_rejection.stderr}":
            raise BackupDrillError("损坏产物虽被拒绝，但没有清晰校验和诊断")

        unsafe_target_rejection = _run(
            _tool_command(
                RUNTIME_ROOT,
                "restore",
                "--archive",
                container_archive,
                "--manifest",
                container_manifest,
                "--key-file",
                "/run/secrets/backup_key",
                "--target-host",
                TARGET_HOST,
                "--target-database",
                "learning_platform",
                "--target-environment",
                ENVIRONMENT,
                "--target-password-file",
                "/run/secrets/postgres_password",
            ),
            stage="不安全恢复目标拒绝演练",
            expect_failure=True,
        )
        if "可丢弃恢复库" not in f"{unsafe_target_rejection.stdout}\n{unsafe_target_rejection.stderr}":
            raise BackupDrillError("不安全目标虽被拒绝，但没有清晰目标诊断")

        restore_started = time.perf_counter()
        _run(
            _tool_command(
                RUNTIME_ROOT,
                "restore",
                "--archive",
                container_archive,
                "--manifest",
                container_manifest,
                "--key-file",
                "/run/secrets/backup_key",
                "--target-host",
                TARGET_HOST,
                "--target-database",
                TARGET_DATABASE,
                "--target-environment",
                ENVIRONMENT,
                "--target-password-file",
                "/run/secrets/postgres_password",
            ),
            stage="真实隔离 pg_restore",
        )
        restore_elapsed = round(time.perf_counter() - restore_started, 3)
        target_fingerprint = parse_probe_fingerprint(
            _psql(TARGET_HOST, TARGET_DATABASE, PROBE_QUERY)
        )
        source_after = parse_probe_fingerprint(
            _psql(SOURCE_HOST, SOURCE_DATABASE, PROBE_QUERY)
        )
        if source_before != source_after:
            raise BackupDrillError("备份或恢复演练改变了源数据库指纹")

        _run(
            _tool_command(
                RUNTIME_ROOT,
                "retention-plan",
                "--backup-dir",
                "/evidence/backups/primary",
                "--keep-days",
                "35",
            ),
            stage="保留策略 dry-run",
        )

        created_at = datetime.fromisoformat(str(manifest["created_at"]))
        rpo_age_minutes = round((datetime.now(UTC) - created_at).total_seconds() / 60, 3)
        report = {
            "status": "passed",
            "backup_id": manifest.get("backup_id"),
            "source": {
                "host": SOURCE_HOST,
                "database": SOURCE_DATABASE,
                "environment": ENVIRONMENT,
                "fingerprint_before": source_before,
                "fingerprint_after": source_after,
                "unchanged": source_before == source_after,
            },
            "target": {
                "host": TARGET_HOST,
                "database": TARGET_DATABASE,
                "environment": ENVIRONMENT,
                "fingerprint": target_fingerprint,
            },
            "encryption": manifest.get("encryption"),
            "sha256": manifest.get("sha256"),
            "replica": manifest.get("replica"),
            "rpo_target_minutes": manifest.get("rpo_target_minutes"),
            "rpo_observed_age_minutes": rpo_age_minutes,
            "rto_target_minutes": manifest.get("rto_target_minutes"),
            "restore_observed_seconds": restore_elapsed,
            "checksum_failure_rejected": True,
            "unsafe_target_rejected": True,
            "production_offsite_verified": False,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        report_path = ACCEPTANCE_ROOT / "drill-report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "恢复演练通过："
            f"source_fingerprint={source_before} target_fingerprint={target_fingerprint} "
            f"restore_seconds={restore_elapsed:.3f}"
        )
        print(f"恢复演练报告：{report_path}")
        return report
    finally:
        _compose(
            *compose,
            "stop",
            SOURCE_HOST,
            TARGET_HOST,
            stage="停止可丢弃数据库",
            echo=False,
        )
        for runtime_file in (key_file, password_file, corrupted_archive):
            runtime_file.unlink(missing_ok=True)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    try:
        run_drill()
    except BackupDrillError as exc:
        print(f"备份恢复演练失败：{redact(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
