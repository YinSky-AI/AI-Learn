"""AI-Learn 本地与 CI 共用的跨平台交付验证编排器。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Step:
    label: str
    command: tuple[str, ...]
    cwd: Path = ROOT


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
        Step("Compose 构建与启动", ("docker", "compose", "up", "-d", "--build", "--wait")),
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
    for index, step in enumerate(steps, start=1):
        print(f"[{index}/{len(steps)}] {step.label}", flush=True)
        try:
            command = _resolve_command(step.command)
        except FileNotFoundError as exc:
            print(f"交付验证失败：{exc}", file=sys.stderr)
            return 2
        result = subprocess.run(
            command,
            cwd=step.cwd,
            check=False,
            env=build_subprocess_env(),
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
