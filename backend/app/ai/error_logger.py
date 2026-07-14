"""
backend/app/ai/error_logger.py

ErrorLogger 中间件 —— 错误捕获、分类和路由模块

本模块作为系统级外环监控组件，实时捕获所有 Agent 执行过程中的错误和异常，
执行标准化分类、严重度评估和路由决策，确保问题可被正确跟踪和处理。

核心职责：
1. 实时捕获所有 Agent 执行过程中的错误和异常
2. 四类分类（SAFE_AUDIT / QUALITY_FAIL / PERF_DEGRADE / LOGIC_ERROR）
3. 路由到对应的处理 Agent
4. 记录错误日志到 ErrorLog 表

关键约束：
- ErrorLogger 不得自行修复错误，只分类和路由
- auto_fix_attempted 恒为 False
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from backend.app.ai.schemas import ErrorEvent, ErrorType, ErrorSeverity

logger = logging.getLogger(__name__)


class ErrorLogger:
    """
    错误捕获和分类中间件

    四类错误分类体系：
    - SAFE_AUDIT (E001-E099): 内容安全违规 → 路由到 SafetyAuditAgent，P0
    - QUALITY_FAIL (E100-E199): 质量检查失败 → 路由到 QualityReviewAgent，P1
    - PERF_DEGRADE (E200-E299): 性能退化 → 路由到 Harness，P2
    - LOGIC_ERROR (E300-E399): 逻辑错误 → 路由到 Harness + SummaryAgent，P1
    """

    # 错误码范围定义
    ERROR_CODE_RANGES = {
        "SAFE_AUDIT": {"start": 1, "end": 99, "prefix": "E"},
        "QUALITY_FAIL": {"start": 100, "end": 199, "prefix": "E"},
        "PERF_DEGRADE": {"start": 200, "end": 299, "prefix": "E"},
        "LOGIC_ERROR": {"start": 300, "end": 399, "prefix": "E"},
    }

    # 路由目标映射
    ROUTING_TARGETS = {
        "SAFE_AUDIT": "SafetyAuditAgent",
        "QUALITY_FAIL": "QualityReviewAgent",
        "PERF_DEGRADE": "Harness",
        "LOGIC_ERROR": "Harness",
    }

    # 严重度映射
    SEVERITY_MAP = {
        "SAFE_AUDIT": ErrorSeverity.P0,
        "QUALITY_FAIL": ErrorSeverity.P1,
        "PERF_DEGRADE": ErrorSeverity.P2,
        "LOGIC_ERROR": ErrorSeverity.P1,
    }

    def __init__(self):
        """初始化 ErrorLogger"""
        # 当前 run 的错误事件缓存
        self._events: list[ErrorEvent] = []
        # 错误计数器（按类型）
        self._counters: dict[str, int] = defaultdict(int)
        # 回调函数：写入数据库
        self._persist_callback: Optional[Any] = None

    def set_persist_callback(self, callback: Any) -> None:
        """
        设置持久化回调函数

        Args:
            callback: 异步回调函数，接收 ErrorEvent 列表
        """
        self._persist_callback = callback

    def reset(self) -> None:
        """
        重置错误缓存（新 run 开始时调用）

        每次新的 Harness Run 开始前必须调用，避免历史错误干扰当前会话统计。
        """
        logger.debug(f"[ErrorLogger] 重置错误缓存，清除 {len(self._events)} 条历史事件")
        self._events.clear()
        self._counters.clear()

    async def capture(
        self,
        agent_name: str,
        step_name: str,
        error_type: str,
        error_code: str,
        severity: str,
        raw_error: str,
        context: Optional[dict[str, Any]] = None,
        affected_output: Optional[dict[str, Any]] = None,
    ) -> ErrorEvent:
        """
        捕获错误事件

        Args:
            agent_name: 出错 Agent 名称
            step_name: 步骤名称
            error_type: 错误类型 (SAFE_AUDIT/QUALITY_FAIL/PERF_DEGRADE/LOGIC_ERROR)
            error_code: 错误编码 (E001-E399)
            severity: 严重度 (P0/P1/P2)
            raw_error: 原始错误信息
            context: 错误上下文
            affected_output: 受影响的输出

        Returns:
            创建的 ErrorEvent
        """
        # 验证并规范化错误类型
        try:
            error_type_enum = ErrorType(error_type)
        except ValueError:
            logger.warning(f"未知错误类型 '{error_type}'，默认使用 LOGIC_ERROR")
            error_type_enum = ErrorType.LOGIC_ERROR

        # 验证并规范化严重度
        try:
            severity_enum = ErrorSeverity(severity)
        except ValueError:
            severity_enum = self.SEVERITY_MAP.get(error_type_enum.value, ErrorSeverity.P1)

        # 确定路由目标
        routing_target = self.ROUTING_TARGETS.get(
            error_type_enum.value, "Harness"
        )

        # 创建错误事件
        event = ErrorEvent(
            timestamp=datetime.utcnow(),
            agent_name=agent_name,
            step_name=step_name,
            error_type=error_type_enum,
            error_code=error_code,
            severity=severity_enum,
            raw_error=raw_error,
            context=context,
            affected_output=affected_output,
            routing_target=routing_target,
            auto_fix_attempted=False,  # 恒为 False
        )

        # 缓存错误事件
        self._events.append(event)
        self._counters[error_type_enum.value] += 1

        logger.error(
            f"[ErrorLogger] 捕获错误 | type={error_type_enum.value} | "
            f"code={error_code} | severity={severity_enum.value} | "
            f"agent={agent_name} | step={step_name} | "
            f"route={routing_target} | error={raw_error[:200]}"
        )

        return event

    async def capture_safe_audit(
        self,
        agent_name: str,
        step_name: str,
        question_id: str,
        reason: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ErrorEvent:
        """
        捕获安全审计否决事件（便捷方法）

        Args:
            agent_name: Agent 名称
            step_name: 步骤名称
            question_id: 被否决的题目 ID
            reason: 否决原因
            context: 上下文

        Returns:
            ErrorEvent
        """
        return await self.capture(
            agent_name=agent_name,
            step_name=step_name,
            error_type="SAFE_AUDIT",
            error_code="E001",
            severity="P0",
            raw_error=f"安全审查否决: {reason}",
            context=context,
            affected_output={"question_id": question_id},
        )

    async def capture_quality_fail(
        self,
        agent_name: str,
        step_name: str,
        question_id: str,
        reason: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ErrorEvent:
        """
        捕获质量检查失败事件（便捷方法）

        Args:
            agent_name: Agent 名称
            step_name: 步骤名称
            question_id: 题目 ID
            reason: 失败原因
            context: 上下文

        Returns:
            ErrorEvent
        """
        return await self.capture(
            agent_name=agent_name,
            step_name=step_name,
            error_type="QUALITY_FAIL",
            error_code="E100",
            severity="P1",
            raw_error=f"质量检查失败: {reason}",
            context=context,
            affected_output={"question_id": question_id},
        )

    async def capture_perf_degrade(
        self,
        agent_name: str,
        step_name: str,
        latency_ms: int,
        threshold_ms: int,
        context: Optional[dict[str, Any]] = None,
    ) -> ErrorEvent:
        """
        捕获性能退化事件（便捷方法）

        Args:
            agent_name: Agent 名称
            step_name: 步骤名称
            latency_ms: 实际耗时
            threshold_ms: 阈值
            context: 上下文

        Returns:
            ErrorEvent
        """
        return await self.capture(
            agent_name=agent_name,
            step_name=step_name,
            error_type="PERF_DEGRADE",
            error_code="E200",
            severity="P2",
            raw_error=f"性能退化: 耗时 {latency_ms}ms，阈值 {threshold_ms}ms",
            context=context,
        )

    async def capture_logic_error(
        self,
        agent_name: str,
        step_name: str,
        error: Exception,
        context: Optional[dict[str, Any]] = None,
    ) -> ErrorEvent:
        """
        捕获逻辑错误事件（便捷方法）

        Args:
            agent_name: Agent 名称
            step_name: 步骤名称
            error: 异常对象
            context: 上下文

        Returns:
            ErrorEvent
        """
        return await self.capture(
            agent_name=agent_name,
            step_name=step_name,
            error_type="LOGIC_ERROR",
            error_code="E300",
            severity="P1",
            raw_error=f"{type(error).__name__}: {str(error)}",
            context=context,
        )

    @property
    def events(self) -> list[ErrorEvent]:
        """
        获取当前 run 的所有错误事件

        Returns:
            错误事件列表的副本（修改不影响内部状态）
        """
        return self._events.copy()

    @property
    def counters(self) -> dict[str, int]:
        """
        获取错误计数

        Returns:
            按错误类型汇总的计数字典
        """
        return dict(self._counters)

    @property
    def has_critical_errors(self) -> bool:
        """
        是否存在严重错误（P0）

        Returns:
            存在 P0 级错误时返回 True，表示需要立即阻断
        """
        return any(e.severity == ErrorSeverity.P0 for e in self._events)

    @property
    def total_errors(self) -> int:
        """
        错误总数

        Returns:
            当前 run 中已捕获的错误事件总数
        """
        return len(self._events)

    async def flush(self) -> list[ErrorEvent]:
        """
        刷新错误事件（持久化并清空缓存）

        在 Harness Run 结束时调用，将当前会话的所有错误事件写入持久化存储。

        Returns:
            刷新前的错误事件列表
        """
        events = self._events.copy()
        logger.info(f"[ErrorLogger] 开始刷新，共 {len(events)} 条错误事件")

        if self._persist_callback and events:
            try:
                await self._persist_callback(events)
                logger.info(f"[ErrorLogger] 持久化 {len(events)} 条错误事件成功")
            except Exception as e:
                logger.error(f"[ErrorLogger] 持久化失败: {e}")
        else:
            logger.debug("[ErrorLogger] 无持久化回调或无事件，跳过持久化")

        self.reset()
        return events

    def get_summary(self) -> dict[str, Any]:
        """
        获取错误摘要

        生成当前 run 的错误统计摘要，用于报告和监控。

        Returns:
            包含错误总数、严重错误标志、计数器和最近 5 条事件的摘要字典
        """
        return {
            "total_errors": self.total_errors,
            "has_critical": self.has_critical_errors,
            "counters": self.counters,
            "latest_events": [
                {
                    "type": e.error_type.value,
                    "code": e.error_code,
                    "severity": e.severity.value,
                    "agent": e.agent_name,
                    "message": e.raw_error[:200],
                }
                for e in self._events[-5:]  # 最近5条
            ],
        }
