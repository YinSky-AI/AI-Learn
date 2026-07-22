from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from ops.backup.backup_recovery import (
    BackupRecoveryError,
    plan_retention,
    validate_backup_target,
    validate_manifest,
    validate_restore_target,
    verify_file_checksum,
)
from scripts.run_backup_restore_drill import (
    BackupDrillError,
    parse_probe_fingerprint,
    validate_drill_targets,
)


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = ROOT / "test" / ".runtime" / "P0-04"


class BackupRecoverySafetyTests(unittest.TestCase):
    def setUp(self):
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="unit-", dir=RUNTIME_ROOT))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_production_source_backup_requires_explicit_acknowledgement(self):
        with self.assertRaisesRegex(BackupRecoveryError, "生产源备份.*明确确认"):
            validate_backup_target(
                host="primary-db",
                database="learning_platform",
                environment="production",
                allow_production=False,
            )

        validate_backup_target(
            host="primary-db",
            database="learning_platform",
            environment="production",
            allow_production=True,
        )

    def test_restore_rejects_source_database_and_non_disposable_targets(self):
        with self.assertRaisesRegex(BackupRecoveryError, "源数据库"):
            validate_restore_target(
                source_host="postgres-test",
                source_database="learning_platform_test",
                target_host="postgres-test",
                target_database="learning_platform_test",
                target_environment="local",
            )

        with self.assertRaisesRegex(BackupRecoveryError, "可丢弃恢复库"):
            validate_restore_target(
                source_host="postgres-test",
                source_database="learning_platform_test",
                target_host="postgres-restore",
                target_database="learning_platform",
                target_environment="local",
            )

        with self.assertRaisesRegex(BackupRecoveryError, "非生产环境"):
            validate_restore_target(
                source_host="primary-db",
                source_database="learning_platform",
                target_host="recovery-db",
                target_database="learning_platform_restore",
                target_environment="production",
            )

    def test_checksum_verification_stops_on_corruption(self):
        archive = self.temp_dir / "probe.aibak"
        archive.write_bytes(b"encrypted-backup")
        expected = hashlib.sha256(archive.read_bytes()).hexdigest()

        verify_file_checksum(archive, expected)
        archive.write_bytes(b"corrupted")

        with self.assertRaisesRegex(BackupRecoveryError, "校验和"):
            verify_file_checksum(archive, expected)

    def test_manifest_requires_authenticated_encryption_and_replica(self):
        manifest = {
            "format_version": 1,
            "encryption": "AES-256-GCM",
            "replica": {"status": "verified", "domain": "off-host"},
            "sha256": "a" * 64,
        }
        validate_manifest(manifest)

        manifest["encryption"] = "none"
        with self.assertRaisesRegex(BackupRecoveryError, "AES-256-GCM"):
            validate_manifest(manifest)

    def test_retention_only_plans_candidates_without_deleting(self):
        recent = self.temp_dir / "recent.aibak"
        expired = self.temp_dir / "expired.aibak"
        recent.write_bytes(b"recent")
        expired.write_bytes(b"expired")
        now = datetime.now(UTC)
        old_timestamp = (now - timedelta(days=31)).timestamp()
        os.utime(expired, (old_timestamp, old_timestamp))

        candidates = plan_retention([recent, expired], keep_days=30, now=now)

        self.assertEqual(candidates, [expired])
        self.assertTrue(recent.exists())
        self.assertTrue(expired.exists())

    def test_drill_only_accepts_the_fixed_disposable_source_and_target(self):
        validate_drill_targets(
            source_host="postgres-test",
            source_database="learning_platform_test",
            target_host="postgres-restore",
            target_database="learning_platform_restore",
            environment="local",
        )

        with self.assertRaisesRegex(BackupDrillError, "固定可丢弃目标"):
            validate_drill_targets(
                source_host="postgres",
                source_database="learning_platform",
                target_host="postgres-restore",
                target_database="learning_platform_restore",
                environment="local",
            )

    def test_restore_probe_requires_rows_unique_values_and_constraints(self):
        fingerprint = parse_probe_fingerprint("2|2|2")
        self.assertEqual(
            fingerprint,
            {"row_count": 2, "unique_markers": 2, "constraints": 2},
        )

        with self.assertRaisesRegex(BackupDrillError, "恢复指纹"):
            parse_probe_fingerprint("2|1|2")


if __name__ == "__main__":
    unittest.main()
