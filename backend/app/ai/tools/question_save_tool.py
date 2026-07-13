"""
题目保存工具 — QuestionSaveTool

将生成的题目保存到数据库（GeneratedQuestion 表）。
同时记录生成批次（GeneratedQuestionBatch 表）。

关键约束：
- 安全审查否决的题目不进入知识库
- 所有保存操作记录 ToolCallLog
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QuestionSaveTool:
    """
    题目保存工具

    负责将经过质量检查和安全审查的题目保存到数据库。
    """

    tool_name = "QuestionSaveTool"

    def __init__(self, db_session=None):
        """
        初始化保存工具

        Args:
            db_session: SQLAlchemy 数据库会话
        """
        self._db_session = db_session

    def set_db_session(self, db_session: Any) -> None:
        """设置数据库会话"""
        self._db_session = db_session

    async def save_batch(
        self,
        batch_id: str,
        user_id: str,
        questions: list[dict[str, Any]],
        batch_meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        保存一批生成的题目

        Args:
            batch_id: 批次 ID
            user_id: 用户 ID
            questions: 通过审查的题目列表
            batch_meta: 批次元信息

        Returns:
            保存结果 {saved_count, batch_id, skipped_count}
        """
        start_time = time.monotonic()

        if not self._db_session:
            logger.warning("[QuestionSaveTool] 无数据库会话，跳过保存")
            return {
                "saved_count": 0,
                "batch_id": batch_id,
                "skipped_count": len(questions),
                "message": "无数据库会话",
            }

        try:
            # TODO: 当数据库模型就绪后实现实际保存
            # 1. 创建/更新 GeneratedQuestionBatch
            # 2. 批量创建 GeneratedQuestion
            # 3. 记录题目质量检查结果

            saved_count = 0
            skipped_count = len(questions)

            latency_ms = int((time.monotonic() - start_time) * 1000)
            result = {
                "saved_count": saved_count,
                "batch_id": batch_id,
                "skipped_count": skipped_count,
                "latency_ms": latency_ms,
            }

            logger.info(
                f"[QuestionSaveTool] 批次保存完成: "
                f"batch={batch_id} | saved={saved_count} | "
                f"skipped={skipped_count} | latency={latency_ms}ms"
            )

            return result

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                f"[QuestionSaveTool] 保存失败 | batch={batch_id} | "
                f"latency={latency_ms}ms | {e}"
            )
            return {
                "saved_count": 0,
                "batch_id": batch_id,
                "skipped_count": len(questions),
                "latency_ms": latency_ms,
                "error": str(e),
            }

    def get_tool_call_record(
        self,
        step_name: str,
        input_summary: dict[str, Any],
        output_summary: Optional[dict[str, Any]] = None,
        latency_ms: int = 0,
        status: str = "succeeded",
        error_message: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        生成工具调用日志记录
        """
        return {
            "step_name": step_name,
            "tool_name": self.tool_name,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "latency_ms": latency_ms,
            "status": status,
            "error_message": error_message,
        }
