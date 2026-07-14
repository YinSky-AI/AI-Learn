"""
backend/app/ai/provider.py

AI Provider 封装 —— OpenAI API 调用管理模块

本模块负责与 DeepSeek / OpenAI 等大模型 API 的交互，提供统一的异步调用接口。
核心功能：
- 支持流式 SSE 输出（generate_stream）
- 错误重试机制（指数退避）
- Token 用量记录与统计
- 多模型支持

设计原则：
- 所有 AI 调用必须经过本模块，禁止旁路调用
- 超时、重试、降级策略集中管理
- Token 用量透明可观测

v0.1 约束：
- 不实现联网搜索
- AI 回复必须经过安全过滤
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Optional

from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)

# 默认模型配置（DeepSeek）
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7
# 最大重试次数
MAX_RETRIES = 3
# 重试基础等待时间（秒）
RETRY_BASE_WAIT = 1.0
# 最大等待时间（秒）
RETRY_MAX_WAIT = 30.0


# 使用简单字典代替避免循环依赖
class AIProvider:
    """
    OpenAI API 调用封装

    支持：
    - 同步调用（generate）
    - 流式 SSE 调用（generate_stream）
    - 自动重试（指数退避）
    - Token 用量记录
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        default_max_tokens: int = DEFAULT_MAX_TOKENS,
        default_temperature: float = DEFAULT_TEMPERATURE,
        max_retries: int = MAX_RETRIES,
        timeout: float = 60.0,
    ):
        """
        初始化 AI Provider

        Args:
            api_key: DeepSeek API Key，默认从环境变量 DEEPSEEK_API_KEY 读取
            base_url: API 基础 URL，默认从环境变量 DEEPSEEK_BASE_URL 读取
            model: 默认模型名称
            default_max_tokens: 默认最大 Token 数
            default_temperature: 默认温度参数
            max_retries: 最大重试次数
            timeout: 请求超时时间（秒）
        """
        import os

        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", None)
        self.model = model
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature
        self.max_retries = max_retries
        self.timeout = timeout

        # 初始化 AsyncOpenAI 客户端
        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": timeout,
        }
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self._client = AsyncOpenAI(**client_kwargs)

        # Token 用量累计
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_requests = 0

    def _record_usage(self, usage: Optional[dict[str, Any]]) -> dict[str, int]:
        """
        记录 Token 用量

        累加本次请求的 Token 消耗到全局统计中，便于成本监控和用量告警。

        Args:
            usage: API 返回的用量字典，包含 prompt_tokens / completion_tokens / total_tokens

        Returns:
            标准化后的用量字典
        """
        if usage:
            # 累加各维度 Token 数
            self._total_prompt_tokens += usage.get("prompt_tokens", 0)
            self._total_completion_tokens += usage.get("completion_tokens", 0)
            self._total_requests += 1
            logger.debug(
                f"[AIProvider] Token 用量记录: prompt={usage.get('prompt_tokens', 0)} | "
                f"completion={usage.get('completion_tokens', 0)}"
            )
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    async def _retry_call(
        self,
        func: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        带指数退避的重试逻辑

        Args:
            func: 异步调用函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数调用结果

        Raises:
            APIError: 重试耗尽后抛出最后一次异常
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except RateLimitError as e:
                last_error = e
                # 速率限制错误，等待更长时间
                wait_time = min(
                    RETRY_BASE_WAIT * (2 ** attempt) * 2,
                    RETRY_MAX_WAIT,
                )
                logger.warning(
                    f"AI Provider 速率限制，第 {attempt + 1}/{self.max_retries} 次重试，"
                    f"等待 {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)
            except APITimeoutError as e:
                last_error = e
                # 超时错误
                wait_time = min(
                    RETRY_BASE_WAIT * (2 ** attempt),
                    RETRY_MAX_WAIT,
                )
                logger.warning(
                    f"AI Provider 请求超时，第 {attempt + 1}/{self.max_retries} 次重试，"
                    f"等待 {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)
            except APIError as e:
                last_error = e
                # 其他 API 错误（5xx 服务端错误才重试）
                if e.status_code and e.status_code >= 500:
                    wait_time = min(
                        RETRY_BASE_WAIT * (2 ** attempt),
                        RETRY_MAX_WAIT,
                    )
                    logger.warning(
                        f"AI Provider 服务端错误 ({e.status_code})，"
                        f"第 {attempt + 1}/{self.max_retries} 次重试，"
                        f"等待 {wait_time:.1f}s"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # 4xx 客户端错误不重试
                    raise
            except Exception as e:
                last_error = e
                # 未知错误也重试
                wait_time = min(
                    RETRY_BASE_WAIT * (2 ** attempt),
                    RETRY_MAX_WAIT,
                )
                logger.warning(
                    f"AI Provider 未知错误 ({type(e).__name__})，"
                    f"第 {attempt + 1}/{self.max_retries} 次重试，"
                    f"等待 {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)

        # 重试耗尽
        logger.error(f"AI Provider 重试耗尽（{self.max_retries}次），最后错误: {last_error}")
        raise last_error  # type: ignore

    async def generate(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[dict[str, str]] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        同步生成（非流式）

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            model: 模型名称，默认使用初始化时的模型
            max_tokens: 最大 Token 数
            temperature: 温度参数
            response_format: 响应格式，如 {"type": "json_object"}
            tools: 工具定义列表（function calling）
            tool_choice: 工具选择策略

        Returns:
            响应字典，包含 content, usage, model, latency_ms
        """
        start_time = time.monotonic()
        use_model = model or self.model
        use_max_tokens = max_tokens or self.default_max_tokens
        use_temperature = temperature if temperature is not None else self.default_temperature

        kwargs: dict[str, Any] = {
            "model": use_model,
            "messages": messages,
            "max_tokens": use_max_tokens,
            "temperature": use_temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        try:
            response = await self._retry_call(self._client.chat.completions.create, **kwargs)

            latency_ms = int((time.monotonic() - start_time) * 1000)
            usage = self._record_usage(
                response.usage.model_dump() if response.usage else None
            )

            content = ""
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content or ""

            return {
                "content": content,
                "model": use_model,
                "usage": usage,
                "latency_ms": latency_ms,
                "finish_reason": (
                    response.choices[0].finish_reason
                    if response.choices
                    else None
                ),
            }

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"AI Provider 生成失败（{latency_ms}ms）: {e}")
            raise

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成（SSE）

        Args:
            messages: 消息列表
            model: 模型名称
            max_tokens: 最大 Token 数
            temperature: 温度参数

        Yields:
            每个 chunk 的文本内容
        """
        use_model = model or self.model
        use_max_tokens = max_tokens or self.default_max_tokens
        use_temperature = temperature if temperature is not None else self.default_temperature

        kwargs: dict[str, Any] = {
            "model": use_model,
            "messages": messages,
            "max_tokens": use_max_tokens,
            "temperature": use_temperature,
            "stream": True,
        }

        try:
            stream = await self._retry_call(
                self._client.chat.completions.create, **kwargs
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content

        except Exception as e:
            logger.error(f"AI Provider 流式生成失败: {e}")
            raise

    @property
    def total_usage(self) -> dict[str, int]:
        """
        获取累计 Token 用量

        Returns:
            包含 prompt_tokens、completion_tokens、total_tokens、total_requests 的字典
        """
        return {
            "prompt_tokens": self._total_prompt_tokens,
            "completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "total_requests": self._total_requests,
        }

    def reset_usage(self) -> None:
        """
        重置 Token 用量统计

        通常在新的统计周期开始时调用（如单次 Harness Run 结束后）。
        """
        logger.info("[AIProvider] Token 用量统计已重置")
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_requests = 0


# 全局 Provider 实例（懒加载）
_provider_instance: Optional[AIProvider] = None


def get_ai_provider() -> AIProvider:
    """
    获取全局 AI Provider 实例（单例模式）

    首次调用时自动初始化，后续调用返回同一实例。
    单例模式确保全局共享同一个连接池和用量统计。

    Returns:
        AIProvider 全局实例
    """
    global _provider_instance
    if _provider_instance is None:
        logger.info("[AIProvider] 初始化全局 Provider 实例")
        _provider_instance = AIProvider()
    return _provider_instance


def reset_ai_provider() -> None:
    """
    重置全局 AI Provider 实例（用于测试和故障恢复）

    重置后下次调用 get_ai_provider() 将创建新实例。
    """
    global _provider_instance
    logger.info("[AIProvider] 全局 Provider 实例已重置")
    _provider_instance = None
