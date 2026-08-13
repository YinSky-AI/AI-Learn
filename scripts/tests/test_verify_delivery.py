import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from scripts.verify_delivery import (
    DeliveryVerificationError,
    build_parser,
    parse_compose_status,
    redact,
    validate_health_payload,
)
from scripts.run_backend_tests import validate_test_database_url
from scripts.verify import (
    build_steps,
    build_subprocess_env,
    managed_full_gate_environment,
)


ROOT = Path(__file__).resolve().parents[2]


class DeliveryVerificationTests(unittest.TestCase):
    def test_compose_config_does_not_require_a_local_backend_env_file(self):
        docker = shutil.which("docker")
        if docker is None:
            self.skipTest("docker is required to validate the Compose contract")

        with tempfile.TemporaryDirectory() as temp_dir:
            compose_path = Path(temp_dir) / "docker-compose.yml"
            compose_path.write_text(
                (ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = subprocess.run(
                [docker, "compose", "-f", str(compose_path), "config", "--profiles"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_smoke_uses_the_public_gateway_by_default(self):
        args = build_parser().parse_args([])

        self.assertEqual(args.frontend_url, "http://localhost")

    def test_cross_platform_full_gate_contains_every_delivery_layer(self):
        labels = [step.label for step in build_steps("full")]
        self.assertEqual(
            labels,
            [
                "交付脚本单元测试",
                "方程诊断规则评测",
                "前端测试",
                "前端类型检查",
                "前端生产构建",
                "后端镜像构建",
                "隔离后端测试",
                "加密备份与隔离恢复演练",
                "双数据库 Schema 迁移演练",
                "Compose 依赖服务启动",
                "Compose 主业务库 bootstrap",
                "Compose 题库 bootstrap",
                "Compose 构建与启动",
                "Docker smoke",
                "真实浏览器 E2E",
            ],
        )
        self.assertIn("discover", build_steps("fast")[0].command)

    def test_full_gate_bootstraps_empty_compose_databases_before_strict_start(self):
        steps = build_steps("full")
        labels = [step.label for step in steps]
        primary = steps[labels.index("Compose 主业务库 bootstrap")]
        catalog = steps[labels.index("Compose 题库 bootstrap")]
        start = steps[labels.index("Compose 构建与启动")]

        self.assertLess(labels.index(primary.label), labels.index(start.label))
        self.assertLess(labels.index(catalog.label), labels.index(start.label))
        self.assertIn("schema-bootstrap-primary", primary.command)
        self.assertIn("schema-bootstrap-catalog", catalog.command)
        self.assertEqual(dict(start.environment)["SCHEMA_VERSION_POLICY"], "strict")

    def test_full_gate_runs_both_alembic_drift_checks(self):
        backend_step = next(
            step for step in build_steps("full") if step.label == "隔离后端测试"
        )

        self.assertIn("run_backend_tests.py", " ".join(backend_step.command))
        runner = (ROOT / "scripts" / "run_backend_tests.py").read_text(encoding="utf-8")
        self.assertIn('"check"', runner)
        self.assertIn('"/run/secrets/primary_database_url"', runner)
        self.assertIn('"/run/secrets/catalog_database_url"', runner)

    def test_backend_test_runner_removes_the_disposable_database_by_default(self):
        runner = (ROOT / "scripts" / "run_backend_tests.py").read_text(encoding="utf-8")

        self.assertIn('os.getenv("KEEP_TEST_DB")', runner)
        self.assertIn('[*compose, "rm", "-sf", "postgres-test"]', runner)

    def test_backend_tests_never_recreate_schema_from_orm_metadata(self):
        sources = [
            ROOT / "backend" / "tests" / "conftest.py",
            ROOT / "backend" / "tests" / "test_question_generation_api.py",
        ]

        for source in sources:
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("Base.metadata.create_all", text)
            self.assertNotIn("Base.metadata.drop_all", text)

    def test_subprocesses_are_forced_to_emit_utf8_diagnostics(self):
        environment = build_subprocess_env({"PATH": "example"})
        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(environment["PYTHONUTF8"], "1")

    def test_clean_full_gate_creates_file_only_secrets_without_bom_and_cleans_them(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "delivery-full"
            with managed_full_gate_environment(runtime_root, {}) as environment:
                secret_paths = {
                    Path(environment["POSTGRES_PASSWORD_SECRET_FILE"]),
                    Path(environment["PRIMARY_DATABASE_URL_SECRET_FILE"]),
                    Path(environment["CATALOG_DATABASE_URL_SECRET_FILE"]),
                }
                self.assertEqual(environment["DELIVERY_TEST_ENV"], "ci")
                self.assertTrue(all(path.is_file() for path in secret_paths))
                for path in secret_paths:
                    self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                self.assertNotIn("postgresql+asyncpg://", " ".join(environment.values()))

            self.assertTrue(all(not path.exists() for path in secret_paths))

    def test_full_gate_secret_paths_never_appear_in_step_argv(self):
        commands = "\n".join(
            " ".join(step.command) for step in build_steps("full")
        )

        self.assertNotIn("POSTGRES_PASSWORD_SECRET_FILE", commands)
        self.assertNotIn("PRIMARY_DATABASE_URL_SECRET_FILE", commands)
        self.assertNotIn("CATALOG_DATABASE_URL_SECRET_FILE", commands)

    def test_full_gate_reuses_complete_external_secrets_without_cleaning_them(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            secret_root = Path(temp_dir).resolve()
            password = "existing-volume-password"
            encoded = quote(password, safe="")
            password_file = secret_root / "password"
            primary_file = secret_root / "primary"
            catalog_file = secret_root / "catalog"
            password_file.write_text(password + "\n", encoding="utf-8")
            primary_file.write_text(
                "postgresql+asyncpg://postgres:"
                f"{encoded}@postgres:5432/learning_platform\n",
                encoding="utf-8",
            )
            catalog_file.write_text(
                "postgresql+asyncpg://postgres:"
                f"{encoded}@postgres:5432/ai_learn\n",
                encoding="utf-8",
            )
            source = {
                "POSTGRES_PASSWORD_SECRET_FILE": str(password_file),
                "PRIMARY_DATABASE_URL_SECRET_FILE": str(primary_file),
                "CATALOG_DATABASE_URL_SECRET_FILE": str(catalog_file),
            }

            with managed_full_gate_environment(
                secret_root / "unused", source
            ) as environment:
                self.assertEqual(environment["DELIVERY_TEST_ENV"], "ci")
                self.assertEqual(
                    environment["POSTGRES_PASSWORD_SECRET_FILE"],
                    str(password_file),
                )

            self.assertTrue(password_file.is_file())
            self.assertTrue(primary_file.is_file())
            self.assertTrue(catalog_file.is_file())

    def test_full_gate_rejects_partial_external_secret_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            password_file = Path(temp_dir).resolve() / "password"
            password_file.write_text("sentinel\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "必须同时提供"):
                with managed_full_gate_environment(
                    Path(temp_dir) / "runtime",
                    {"POSTGRES_PASSWORD_SECRET_FILE": str(password_file)},
                ):
                    self.fail("部分 secret 不得进入 full gate")

    def test_backend_test_runner_rejects_non_disposable_database_targets(self):
        target = validate_test_database_url(
            "postgresql+asyncpg://postgres:sentinel@postgres-test:5432/learning_platform_test",
            "local",
        )
        self.assertEqual(target, ("postgres-test", "learning_platform_test", "local"))

        with self.assertRaisesRegex(ValueError, "可丢弃测试数据库"):
            validate_test_database_url(
                "postgresql+asyncpg://postgres:sentinel@postgres:5432/learning_platform",
                "local",
            )

    def test_schema_paths_use_secret_files_and_keep_backend_image_cmd(self):
        sources = {
            "compose": (ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
            "backend runner": (ROOT / "scripts" / "run_backend_tests.py").read_text(
                encoding="utf-8"
            ),
            "migration drill": (
                ROOT / "scripts" / "run_schema_migration_drill.py"
            ).read_text(encoding="utf-8"),
        }
        for label, source in sources.items():
            self.assertNotIn("postgres:postgres", source, label)
        self.assertNotIn('"--database-url",', sources["backend runner"])
        self.assertNotIn('"--database-url",', sources["migration drill"])
        self.assertIn("--database-url-file", sources["compose"])

        dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn('CMD ["python", "run.py"]', dockerfile)

    def test_pytest_fixture_requires_a_validated_file_only_disposable_target(self):
        conftest = (ROOT / "backend" / "tests" / "conftest.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('os.getenv("TEST_DATABASE_URL")', conftest)
        self.assertNotIn("postgres:postgres", conftest)
        self.assertIn("TEST_DATABASE_URL_FILE", conftest)
        self.assertIn("validate_test_database_target", conftest)

    def test_readme_commands_match_file_only_make_contracts(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("primary_database_url_file=", readme)
        self.assertIn("catalog_database_url_file=", readme)
        self.assertIn("postgres_password_file=", readme)
        self.assertIn("database_url_file=", readme)
        self.assertNotIn("database_url='<secret-injected-url>'", readme)

    def test_health_contract_requires_healthy_status(self):
        validate_health_payload(
            {
                "code": "SUCCESS",
                "message": "服务运行正常",
                "data": {"status": "healthy"},
            }
        )

        with self.assertRaisesRegex(DeliveryVerificationError, "健康端点状态不是 healthy"):
            validate_health_payload({"code": "SUCCESS", "data": {"status": "degraded"}})

    def test_compose_status_requires_running_and_healthy_services(self):
        rows = [
            {"Service": "postgres", "State": "running", "Health": "healthy"},
            {"Service": "redis", "State": "running", "Health": "healthy"},
            {"Service": "backend", "State": "running", "Health": "healthy"},
            {"Service": "frontend", "State": "running", "Health": "healthy"},
            {"Service": "nginx-gateway", "State": "running", "Health": "healthy"},
        ]

        parsed = parse_compose_status("\n".join(__import__("json").dumps(row) for row in rows))
        self.assertEqual(set(parsed), {row["Service"] for row in rows})

        rows[2]["Health"] = "unhealthy"
        with self.assertRaisesRegex(DeliveryVerificationError, "backend.*unhealthy"):
            parse_compose_status("\n".join(__import__("json").dumps(row) for row in rows))

    def test_sensitive_values_are_redacted_from_diagnostics(self):
        message = (
            "postgresql+asyncpg://student:secret@db:5432/test "
            "Authorization: Bearer abc.def.ghi password=hunter2"
        )

        cleaned = redact(message)

        self.assertNotIn("secret", cleaned)
        self.assertNotIn("abc.def.ghi", cleaned)
        self.assertNotIn("hunter2", cleaned)
        self.assertIn("***", cleaned)


if __name__ == "__main__":
    unittest.main()
