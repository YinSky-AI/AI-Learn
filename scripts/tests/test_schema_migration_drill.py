from __future__ import annotations

import unittest
from pathlib import Path

from backend.app.core.schema_version import get_expected_schema_revision
from scripts.run_schema_migration_drill import (
    PRIMARY_HEAD,
    SchemaMigrationDrillError,
    assert_no_secret_material,
    assert_revision_observation,
    content_digest,
    parse_tmpfs_mounts,
    validate_schema_drill_targets,
)


class SchemaMigrationDrillSafetyTests(unittest.TestCase):
    def test_primary_drill_head_matches_the_runtime_schema_contract(self):
        self.assertEqual(PRIMARY_HEAD, get_expected_schema_revision("primary"))

    def test_partial_failure_retries_catalog_single_entry_before_aggregate_repeat(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "run_schema_migration_drill.py"
        ).read_text(encoding="utf-8")

        retry = source.index('catalog_single_entry_retry = _compose_release_bootstrap(')
        aggregate = source.index("aggregate_repeat = _compose_release_bootstrap_all()")
        self.assertLess(retry, aggregate)
        self.assertIn('"catalog_single_entry_retry": {', source)
        self.assertIn('"primary_unchanged": True', source)
        self.assertIn('DRILL_SECRET_ROOT = RUNTIME_ROOT / "drill-secrets"', source)
        self.assertNotIn('return RUNTIME_ROOT / "secrets" / filename', source)

    def test_legacy_fixture_downgrades_both_databases_before_removing_version_stamps(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "run_schema_migration_drill.py"
        ).read_text(encoding="utf-8")
        catalog_downgrade = source.index('alias="question-bank", host=SOURCE_HOST')
        catalog_stamp_drop = source.index('DROP TABLE alembic_version_catalog;')
        self.assertLess(catalog_downgrade, catalog_stamp_drop)

    def test_drill_accepts_only_the_four_fixed_tmpfs_databases(self):
        validate_schema_drill_targets(
            source_host="postgres-test",
            primary_source_database="learning_platform_test",
            catalog_source_database="ai_learn_test",
            restore_host="postgres-restore",
            primary_restore_database="learning_platform_restore",
            catalog_restore_database="ai_learn_restore",
            environment="local",
        )

        with self.assertRaisesRegex(SchemaMigrationDrillError, "固定的四个可丢弃"):
            validate_schema_drill_targets(
                source_host="postgres",
                primary_source_database="learning_platform",
                catalog_source_database="ai_learn",
                restore_host="postgres-restore",
                primary_restore_database="learning_platform_restore",
                catalog_restore_database="ai_learn_restore",
                environment="local",
            )

    def test_revision_report_requires_a_real_observation_for_every_transition(self):
        self.assertEqual(
            assert_revision_observation(
                stage="primary baseline to base",
                actual=None,
                expected=None,
                managed_table_count=0,
            ),
            {"revision": "base", "managed_table_count": 0},
        )

        with self.assertRaisesRegex(SchemaMigrationDrillError, "revision"):
            assert_revision_observation(
                stage="primary baseline to base",
                actual="lp_0001_legacy_baseline",
                expected=None,
                managed_table_count=30,
            )

    def test_tmpfs_storage_claim_requires_the_database_data_mount(self):
        mounts = parse_tmpfs_mounts(
            '{"Mounts":[{"Type":"bind","Destination":"/docker-entrypoint-initdb.d/01-init-db.sql"}],'
            '"HostConfig":{"Tmpfs":{"/var/lib/postgresql/data":""}}}'
        )
        self.assertEqual(mounts, {"/var/lib/postgresql/data"})

        with self.assertRaisesRegex(SchemaMigrationDrillError, "tmpfs"):
            parse_tmpfs_mounts(
                '{"Mounts":[{"Type":"volume","Destination":"/var/lib/postgresql/data"}],'
                '"HostConfig":{"Tmpfs":null}}'
            )

    def test_content_digest_is_order_independent_but_content_sensitive(self):
        first = content_digest(
            {"questions": ["row-b", "row-a"], "users": ["user-a"]}
        )
        reordered = content_digest(
            {"users": ["user-a"], "questions": ["row-a", "row-b"]}
        )
        changed = content_digest(
            {"questions": ["row-a", "row-c"], "users": ["user-a"]}
        )

        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)

    def test_secret_material_is_rejected_from_metadata_payloads(self):
        assert_no_secret_material(
            stage="container metadata",
            payload='{"Cmd":["python","run.py"],"Env":["DATABASE_URL_FILE=/run/secrets/db"]}',
            secret_values=("sentinel-password", "sentinel-dsn"),
        )
        with self.assertRaisesRegex(SchemaMigrationDrillError, "泄露"):
            assert_no_secret_material(
                stage="container metadata",
                payload='{"Env":["DATABASE_URL=sentinel-dsn"]}',
                secret_values=("sentinel-dsn",),
            )


if __name__ == "__main__":
    unittest.main()
