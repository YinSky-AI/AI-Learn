import unittest

from scripts.verify_delivery import (
    DeliveryVerificationError,
    build_parser,
    parse_compose_status,
    redact,
    validate_health_payload,
)
from scripts.run_backend_tests import validate_test_database_url
from scripts.verify import build_steps, build_subprocess_env


class DeliveryVerificationTests(unittest.TestCase):
    def test_smoke_uses_the_public_gateway_by_default(self):
        args = build_parser().parse_args([])

        self.assertEqual(args.frontend_url, "http://localhost")

    def test_cross_platform_full_gate_contains_every_delivery_layer(self):
        labels = [step.label for step in build_steps("full")]
        self.assertEqual(
            labels,
            [
                "交付脚本单元测试",
                "前端测试",
                "前端类型检查",
                "前端生产构建",
                "后端镜像构建",
                "隔离后端测试",
                "Compose 构建与启动",
                "Docker smoke",
                "真实浏览器 E2E",
            ],
        )

    def test_subprocesses_are_forced_to_emit_utf8_diagnostics(self):
        environment = build_subprocess_env({"PATH": "example"})
        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(environment["PYTHONUTF8"], "1")

    def test_backend_test_runner_rejects_non_disposable_database_targets(self):
        target = validate_test_database_url(
            "postgresql+asyncpg://postgres:postgres@postgres-test:5432/learning_platform_test",
            "local",
        )
        self.assertEqual(target, ("postgres-test", "learning_platform_test", "local"))

        with self.assertRaisesRegex(ValueError, "可丢弃测试数据库"):
            validate_test_database_url(
                "postgresql+asyncpg://postgres:postgres@postgres:5432/learning_platform",
                "local",
            )

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
