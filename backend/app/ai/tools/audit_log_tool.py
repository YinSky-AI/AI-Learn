"""
backend/app/ai/tools/audit_log_tool.py

审计日志工具 —— AuditLogTool

本模块负责记录 AI Harness 执行过程中的全部审计事件，
构建可追溯的审计链路，支持安全合规和故障排查。

记录的审计信息包括：
- 安全审查结果（SafetyAudit）
- 质量检查结果（QualityCheck）
- 控制信号（ControlSignal）
- 工具调用记录（ToolCallRecord）

设计特点：
- 内存缓存 + 批量持久化架构，降低数据库写入压力
- 所有记录携带时间戳和 run_id，支持跨会话关联
- 审计与业务逻辑解耦，不影响主流程性能
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditLogTool:
    """
    审计日志工具

    记录所有审计相关事件，确保可追溯。
    """

    tool_name = "AuditLogTool"

    def __init__(self, db_session=None):
        """初始化审计日志工具"""
        self._db_session = db_session
        # 内存中的审计记录缓存
        self._audit_cache: list[dict[str, Any]] = []

    def set_db_session(self, db_session: Any) -> None:
        """设置数据库会话"""
        self._db_session = db_session

    async def log_safety_audit(
        self,
        question_id: str,
        verdict: str,
        scores: dict[str, float],
        issues: list[dict[str, Any]],
        blocking_issue: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        记录安全审查结果

        Args:
            question_id: 题目 ID
            verdict: 审查结论 (PASS/REJECT)
            scores: 四维评分
            issues: 问题列表
            blocking_issue: 否决原因
            run_id: Harness Run ID

        Returns:
            日志记录
        """
        record = {
            "tool_name": self.tool_name,
            "action": "safety_audit",
            "question_id": question_id,
            "verdict": verdict,
            "scores": scores,
            "issue_count": len(issues),
            "blocking_issue": blocking_issue,
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._audit_cache.append(record)

        logger.info(
            f"[AuditLogTool] 安全审查记录: qid={question_id} | "
            f"verdict={verdict} | scores={scores}"
        )

        return record

    async def log_quality_check(
        self,
        question_id: str,
        passed: bool,
        score: float,
        issues: list[dict[str, Any]],
        run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        记录质量检查结果

        Args:
            question_id: 题目 ID
            passed: 是否通过
            score: 质量分数
            issues: 问题列表
            run_id: Harness Run ID

        Returns:
            日志记录
        """
        record = {
            "tool_name": self.tool_name,
            "action": "quality_check",
            "question_id": question_id,
            "passed": passed,
            "score": score,
            "issue_count": len(issues),
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._audit_cache.append(record)

        logger.info(
            f"[AuditLogTool] 质量检查记录: qid={question_id} | "
            f"passed={passed} | score={score:.1f}"
        )

        return record

    async def log_control_signal(
        self,
        control_signal: dict[str, Any],
        run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        记录控制信号

        Args:
            control_signal: ControlSignal 字典
            run_id: Harness Run ID

        Returns:
            日志记录
        """
        record = {
            "tool_name": self.tool_name,
            "action": "control_signal",
            "control_signal": control_signal,
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._audit_cache.append(record)

        logger.info(
            f"[AuditLogTool] 控制信号记录: "
            f"diff_delta={control_signal.get('adjustments', {}).get('difficulty_delta', 0)}"
        )

        return record

    def get_audit_cache(self) -> list[dict[str, Any]]:
        """获取内存中的审计记录"""
        return self._audit_cache.copy()

    def clear_cache(self) -> None:
        """清空审计缓存"""
        self._audit_cache.clear()

    def get_tool_call_record(
        self,
        step_name: str,
        input_summary: dict[str, Any],
        output_summary: Optional[dict[str, Any]] = None,
        latency_ms: int = 0,
        status: str = "succeeded",
        error_message: Optional[str] = None,
    ) -> dict[str, Any]:
        """生成工具调用日志记录"""
        return {
            "step_name": step_name,
            "tool_name": self.tool_name,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "latency_ms": latency_ms,
            "status": status,
            "error_message": error_message,
        }
