"""
backend/app/ai/tools/question_memory_tool.py

题目知识库检索工具 —— QuestionMemoryTool

本模块提供生成题目知识库的多维度检索能力，是 L3 QuestionMemoryAgent 的数据支撑层。
使用 PostgreSQL 原生全文检索和模糊匹配能力，实现高效的相似题检测和去重。

v0.1 不实现联网搜索，不调用搜索 API。

核心功能：
- 全文检索（tsvector）：按题干内容、课程主题、知识点标签搜索
- 模糊匹配（pg_trgm）：检测相似题目用于去重
- 历史错题检索：分析用户答题记录中的错误模式
- 用户偏好检索：提取题型、场景、难度倾向等偏好

检索策略（v0.1）：
- 使用 PostgreSQL tsvector 对 question_body、course_topic、knowledge_tags 建全文检索索引
- 使用 pg_trgm 对 question_body 做模糊匹配
- 按用户维度沉淀，优先服务该用户的去重、复习和错题变式

注意：v0.1 的"知识库"是历史生成题 + 答题记录 + 题目指纹的长期沉淀，
不是预置教材库或外部资料库。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QuestionMemoryTool:
    """
    生成题目知识库检索工具

    检索策略（v0.1）：
    - 使用 PostgreSQL tsvector 对 question_body、course_topic、knowledge_tags
      建全文检索索引
    - 使用 pg_trgm 对 question_body 做模糊匹配
    - 按用户维度沉淀，优先服务该用户的去重、复习和错题变式

    注意：v0.1 的"知识库"是历史生成题 + 答题记录 + 题目指纹的长期沉淀，
    不是预置教材库或外部资料库。
    """

    tool_name = "QuestionMemoryTool"

    def __init__(self, db_session=None):
        """
        初始化检索工具

        Args:
            db_session: SQLAlchemy 数据库会话（由 Harness 注入）
        """
        self._db_session = db_session

    def set_db_session(self, db_session: Any) -> None:
        """设置数据库会话"""
        self._db_session = db_session

    async def search_similar_questions(
        self,
        user_id: str,
        subject: str,
        course_topic: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        搜索相似题目（用于去重）

        使用 tsvector 全文检索 + pg_trgm 模糊匹配

        Args:
            user_id: 用户 ID
            subject: 学科
            course_topic: 课程主题
            limit: 返回数量上限

        Returns:
            {
                "questions": [{id, similarity_hash, question_body_preview, similarity_score}],
                "total": 总匹配数
            }
        """
        start_time = time.monotonic()

        # v0.1: 如果没有数据库会话，返回空结果
        if not self._db_session:
            logger.debug("[QuestionMemoryTool] 无数据库会话，返回空结果")
            return {"questions": [], "total": 0}

        try:
            # 构建 tsvector 全文检索查询
            # SELECT id, similarity_hash, LEFT(question_body, 50) as preview,
            #        ts_rank(to_tsvector('zh_simple', question_body || ' ' || course_topic), query) as score
            # FROM generated_questions
            # WHERE user_id = :user_id
            #   AND subject_code = :subject
            #   AND to_tsvector('zh_simple', question_body || ' ' || course_topic) @@ to_tsquery('zh_simple', :topic_query)
            # ORDER BY score DESC
            # LIMIT :limit

            # pg_trgm 模糊匹配
            # SELECT id, similarity_hash, LEFT(question_body, 50) as preview,
            #        similarity(question_body, :target_body) as sim_score
            # FROM generated_questions
            # WHERE user_id = :user_id
            #   AND subject_code = :subject
            #   AND similarity(question_body, :target_body) > 0.3
            # ORDER BY sim_score DESC
            # LIMIT :limit

            # TODO: 当数据库模型就绪后实现实际查询
            result = {"questions": [], "total": 0}

            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                f"[QuestionMemoryTool] 相似题检索: "
                f"user={user_id} | subject={subject} | topic={course_topic} | "
                f"found=0 | latency={latency_ms}ms"
            )

            return result

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                f"[QuestionMemoryTool] 检索失败 | latency={latency_ms}ms | {e}"
            )
            return {"questions": [], "total": 0, "error": str(e)}

    async def search_error_patterns(
        self,
        user_id: str,
        subject: str,
        course_topic: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        搜索用户历史错题模式

        Args:
            user_id: 用户 ID
            subject: 学科
            course_topic: 课程主题
            limit: 返回数量上限

        Returns:
            错题模式列表
        """
        if not self._db_session:
            return []

        try:
            # TODO: 实现错题模式查询
            # 基于用户答题记录中 is_correct=false 的题目
            # 分析共性和模式
            return []

        except Exception as e:
            logger.error(f"[QuestionMemoryTool] 错题模式检索失败: {e}")
            return []

    async def search_user_preferences(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """
        搜索用户偏好

        Args:
            user_id: 用户 ID

        Returns:
            用户偏好字典
        """
        if not self._db_session:
            return {}

        try:
            # TODO: 实现用户偏好查询
            # 基于答题行为分析偏好（题型偏好、场景偏好等）
            return {}

        except Exception as e:
            logger.error(f"[QuestionMemoryTool] 用户偏好检索失败: {e}")
            return {}

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

        Args:
            step_name: 步骤名称
            input_summary: 输入摘要
            output_summary: 输出摘要
            latency_ms: 耗时
            status: 状态
            error_message: 错误信息

        Returns:
            ToolCallRecord 字典
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
