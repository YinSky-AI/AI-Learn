"""可在本地与 CI 共用的脱敏交付 smoke 验证入口。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


EXPECTED_SERVICES = {"postgres", "redis", "backend", "frontend", "nginx-gateway"}
HEALTHCHECK_SERVICES = EXPECTED_SERVICES
FATAL_LOG_PATTERN = re.compile(
    r"(?:\b(?:traceback|unhandled|fatal|panic)\b|connect\(\) failed|no live upstreams)",
    re.IGNORECASE,
)


class DeliveryVerificationError(RuntimeError):
    """交付验证失败，消息可直接显示给执行者。"""


def redact(value: str) -> str:
    """移除诊断文本中的连接凭据、Bearer token 与密码。"""

    value = re.sub(
        r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^\s:/@]+):[^\s@]+@",
        r"\g<scheme>\g<user>:***@",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]+", r"\1***", value)
    return re.sub(r"(?i)(password\s*[=:]\s*)[^\s]+", r"\1***", value)


def validate_health_payload(payload: dict[str, Any]) -> None:
    """验证后端公开健康契约。"""

    if payload.get("code") != "SUCCESS":
        raise DeliveryVerificationError("健康端点未返回 SUCCESS")
    if not isinstance(payload.get("data"), dict) or payload["data"].get("status") != "healthy":
        raise DeliveryVerificationError("健康端点状态不是 healthy")


def _decode_compose_rows(output: str) -> list[dict[str, Any]]:
    stripped = output.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        rows = json.loads(stripped)
        return rows if isinstance(rows, list) else [rows]
    return [json.loads(line) for line in stripped.splitlines() if line.strip()]


def parse_compose_status(output: str) -> dict[str, dict[str, Any]]:
    """解析 ``docker compose ps --format json`` 并强制检查服务状态。"""

    try:
        rows = _decode_compose_rows(output)
    except json.JSONDecodeError as exc:
        raise DeliveryVerificationError("Docker Compose 状态不是有效 JSON") from exc

    services = {str(row.get("Service")): row for row in rows if row.get("Service")}
    missing = sorted(EXPECTED_SERVICES - services.keys())
    if missing:
        raise DeliveryVerificationError(f"缺少运行中的 Compose 服务：{', '.join(missing)}")

    for name in sorted(EXPECTED_SERVICES):
        row = services[name]
        state = str(row.get("State", "")).lower()
        health = str(row.get("Health", "")).lower()
        if state != "running":
            raise DeliveryVerificationError(f"{name} 状态不是 running：{state or 'unknown'}")
        if name in HEALTHCHECK_SERVICES and health != "healthy":
            raise DeliveryVerificationError(f"{name} 健康状态不是 healthy：{health or 'unknown'}")
    return services


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 - URL is operator supplied.
            if response.status != 200:
                raise DeliveryVerificationError(f"{url} 返回 HTTP {response.status}")
            payload = json.load(response)
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise DeliveryVerificationError(f"无法读取健康端点 {url}：{redact(str(exc))}") from exc
    if not isinstance(payload, dict):
        raise DeliveryVerificationError("健康端点未返回 JSON 对象")
    return payload


def _check_frontend(url: str, timeout: float) -> None:
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 - URL is operator supplied.
            if not 200 <= response.status < 400:
                raise DeliveryVerificationError(f"前端返回 HTTP {response.status}")
    except (OSError, URLError) as exc:
        raise DeliveryVerificationError(f"无法访问前端 {url}：{redact(str(exc))}") from exc


def _run_compose(*arguments: str) -> str:
    result = subprocess.run(
        ["docker", "compose", *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        detail = redact((result.stderr or result.stdout).strip())
        raise DeliveryVerificationError(f"Docker Compose 命令失败：{detail}")
    return result.stdout


def verify(args: argparse.Namespace) -> None:
    validate_health_payload(_get_json(f"{args.backend_url.rstrip('/')}/health", args.timeout))
    _check_frontend(f"{args.frontend_url.rstrip('/')}/login", args.timeout)
    if not args.skip_compose:
        parse_compose_status(_run_compose("ps", "--format", "json"))
        logs = _run_compose(
            "logs",
            "--no-color",
            "--since",
            args.logs_since,
            "backend",
            "frontend",
            "postgres",
            "redis",
            "nginx-gateway",
        )
        fatal_line = next((line for line in logs.splitlines() if FATAL_LOG_PATTERN.search(line)), None)
        if fatal_line:
            raise DeliveryVerificationError(f"服务日志包含致命错误：{redact(fatal_line)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="验证 AI-Learn 健康端点、Compose 状态和近期日志")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--frontend-url", default="http://localhost")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--logs-since", default="5m")
    parser.add_argument("--skip-compose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        verify(args)
    except DeliveryVerificationError as exc:
        print(f"交付验证失败：{redact(str(exc))}", file=sys.stderr)
        return 1
    print("交付 smoke 验证通过：后端、前端、Compose 健康状态和近期日志均符合要求。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
