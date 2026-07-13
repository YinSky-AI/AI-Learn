"""
Agent 基类 — 统一接口

所有 Agent 必须继承 BaseAgent，实现统一的执行接口：
- 输入 Schema（Pydantic BaseModel）
- LLM 调用（通过 AIProvider）
- 输出 Schema（Pydantic BaseModel）
- 偏差声明（deviation_declaration）

每个 Agent 的职责：
1. 接收结构化输入
2. 构建 Prompt（通过 Prompt 模板）
3. 调用 LLM 获取响应
4. 解析响应为结构化输出
5. 如果输出偏离设定值，声明偏差
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional, TypeVar

from pydantic import BaseModel

from backend.app.ai.provider import AIProvider, get_ai_provider
from backend.app.ai.error_logger import ErrorLogger

logger = logging.getLogger(__name__)

# 泛型类型：输入和输出 Schema
InputSchema = TypeVar("InputSchema", bound=BaseModel)
OutputSchema = TypeVar("OutputSchema", bound=BaseModel)


class BaseAgent(ABC):
    """
    Agent 基类

    所有 Agent 必须继承此类，实现 execute() 方法。

    生命周期:
    1. __init__: 初始化 Agent 配置
    2. execute: 执行 Agent 逻辑（输入 -> LLM调用 -> 输出）
    3. _build_prompt: 构建 Prompt 消息列表（子类实现）
    4. _parse_response: 解析 LLM 响应为结构化输出（子类实现）
    """

    # Agent 名称（子类必须设置）
    agent_name: str = "BaseAgent"

    # Agent 层级（子类必须设置）
    layer: str = ""

    # 上游 Agent（子类设置）
    upstream_agents: list[str] = []

    # 下游 Agent（子类设置）
    downstream_agents: list[str] = []

    # 输入信号名称（对应接口契约）
    input_signals: list[str] = []

    # 输出信号名称（对应接口契约）
    output_signals: list[str] = []

    # 是否需要 JSON 格式输出
    requires_json_output: bool = True

    # 模型配置
    model: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0.7

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        error_logger: Optional[ErrorLogger] = None,
    ):
        """
        初始化 Agent

        Args:
            provider: AI Provider 实例，默认使用全局单例
            error_logger: ErrorLogger 实例，默认创建新实例
        """
        self._provider = provider or get_ai_provider()
        self._error_logger = error_logger or ErrorLogger()

    async def execute(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        执行 Agent 逻辑

        统一流程：
        1. 构建 Prompt
        2. 调用 LLM
        3. 解析响应
        4. 返回结构化输出

        Args:
            input_data: 输入数据字典
            context: 执行上下文（包含 run_id, control_signal 等）

        Returns:
            结构化输出字典

        Raises:
            Exception: LLM 调用失败或解析失败时
        """
        start_time = time.monotonic()
        run_id = (context or {}).get("run_id", "unknown")

        logger.info(
            f"[{self.agent_name}] 开始执行 | run_id={run_id} | "
            f"input_keys={list(input_data.keys())}"
        )

        try:
            # 步骤1: 构建 Prompt
            messages = self._build_prompt(input_data, context)

            # 步骤2: 调用 LLM
            response = await self._call_llm(messages)

            # 步骤3: 解析响应
            output = self._parse_response(response, input_data, context)

            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                f"[{self.agent_name}] 执行完成 | run_id={run_id} | "
                f"latency={latency_ms}ms | output_keys={list(output.keys())}"
            )

            return output

        except json.JSONDecodeError as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            error_msg = f"LLM 响应 JSON 解析失败: {e}"
            logger.error(f"[{self.agent_name}] {error_msg} | latency={latency_ms}ms")
            await self._report_error(
                error_msg=error_msg,
                error_code="E300",
                error_type="LOGIC_ERROR",
                severity="P1",
                context=input_data,
            )
            raise

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"[{self.agent_name}] 执行失败 | latency={latency_ms}ms | {error_msg}")
            await self._report_error(
                error_msg=error_msg,
                error_code="E300",
                error_type="LOGIC_ERROR",
                severity="P1",
                context=input_data,
            )
            raise

    @abstractmethod
    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """
        构建 Prompt 消息列表（子类必须实现）

        Args:
            input_data: 输入数据
            context: 执行上下文

        Returns:
            消息列表 [{"role": "system/user/assistant", "content": "..."}]
        """
        raise NotImplementedError

    @abstractmethod
    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        解析 LLM 响应为结构化输出（子类必须实现）

        Args:
            response: LLM 响应字典
            input_data: 原始输入数据
            context: 执行上下文

        Returns:
            结构化输出字典
        """
        raise NotImplementedError

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        调用 LLM

        Args:
            messages: 消息列表

        Returns:
            LLM 响应字典 {content, usage, latency_ms, model}
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if self.requires_json_output:
            kwargs["response_format"] = {"type": "json_object"}

        return await self._provider.generate(
            messages=messages,
            **kwargs,
        )

    def _safe_parse_json(self, text: str) -> Any:
        """
        安全解析 JSON 字符串

        尝试从 LLM 输出中提取 JSON，处理各种边界情况。

        Args:
            text: 可能包含 JSON 的文本

        Returns:
            解析后的 Python 对象

        Raises:
            json.JSONDecodeError: 无法解析时
        """
        text = text.strip()

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块（可能被 markdown 代码块包裹）
        import re

        # 匹配 ```json ... ``` 或 ``` ... ```
        json_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        matches = re.findall(json_block_pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # 尝试找到第一个 { 或 [ 开始的 JSON
        for start_char in ["{", "["]:
            start_idx = text.find(start_char)
            if start_idx >= 0:
                try:
                    return json.loads(text[start_idx:])
                except json.JSONDecodeError:
                    continue

        raise json.JSONDecodeError(f"无法从文本中提取 JSON: {text[:200]}", "", 0)

    async def _report_error(
        self,
        error_msg: str,
        error_code: str,
        error_type: str,
        severity: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        通过 ErrorLogger 报告错误

        Args:
            error_msg: 错误信息
            error_code: 错误编码
            error_type: 错误类型
            severity: 严重度
            context: 错误上下文
        """
        await self._error_logger.capture(
            agent_name=self.agent_name,
            step_name=self.layer,
            error_type=error_type,
            error_code=error_code,
            severity=severity,
            raw_error=error_msg,
            context=context,
        )

    def get_deviation_declaration(
        self,
        expected: Any,
        actual: Any,
        deviation_type: str,
        reason: str,
    ) -> dict[str, str]:
        """
        构建偏差声明

        当 Agent 输出偏离设定值时，必须调用此方法生成偏差声明。

        Args:
            expected: 期望值
            actual: 实际值
            deviation_type: 偏差类型
            reason: 偏差原因

        Returns:
            偏差声明字典
        """
        return {
            "type": deviation_type,
            "expected": str(expected),
            "actual": str(actual),
            "reason": reason,
        }
