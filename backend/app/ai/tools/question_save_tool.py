"""
backend/app/ai/tools/question_save_tool.py

题目保存工具 —— QuestionSaveTool

本模块负责将经过质量检查和安全审查的题目批量持久化到数据库，
同时记录生成批次元信息和审题结论，构建完整的题目生命周期档案。

持久化对象：
- GeneratedQuestion 表：单道题目详情（题干、选项、答案、解析、标签等）
- GeneratedQuestionBatch 表：批次元信息（用户、主题、难度等）
- QuestionQualityCheck 表：审题 Agent 的通过结论

关键约束：
- 只有审题 Agent 通过的题目进入知识库
- 事务由调用方统一管理，任一保存失败会回滚整个批次

设计特点：
- 异步批量保存，在一次 flush 中写入批次、题目和审题记录
- 携带完整批次元信息，支持后续追溯和分析
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.question_generation import PROMPT_VERSION as GENERATION_PROMPT_VERSION
from app.ai.prompts.question_review import PROMPT_VERSION as REVIEW_PROMPT_VERSION
from app.models.ai_generated import (
    GeneratedQuestion,
    GeneratedQuestionBatch,
    QuestionQualityCheck,
)
from app.schemas.question import QuestionGenerateRequest

logger = logging.getLogger(__name__)


class QuestionSaveTool:
    """
    题目保存工具

    负责将经过质量检查和安全审查的题目保存到数据库。
    """

    tool_name = "QuestionSaveTool"

    def __init__(self, request: QuestionGenerateRequest):
        """
        初始化保存工具

        Args:
            request: 当前生成请求，包含批次持久化所需元数据
        """
        self._request = request

    @staticmethod
    def compute_similarity_hash(question_body: str) -> str:
        """计算稳定题干指纹，用于同一用户题库内精确去重。"""
        import hashlib

        normalized = " ".join(question_body.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def save_batch(
        self,
        db: AsyncSession,
        result: Any,
        user_id: uuid.UUID,
    ) -> GeneratedQuestionBatch:
        """
        保存一批生成的题目

        Args:
            db: learning_platform 数据库会话；事务由调用方管理
            result: QuestionPipeline 返回的已审题结果
            user_id: 用户 ID

        Returns:
            已持久化的完成批次
        """
        start_time = time.monotonic()
        if not result.review.passed:
            raise ValueError("未通过审题的题目不能保存")

        batch = GeneratedQuestionBatch(
            id=uuid.uuid4(),
            user_id=user_id,
            age_group_code=self._request.age_group_code,
            subject_code=self._request.subject_code,
            course_topic=self._request.course_topic,
            difficulty_level=self._request.difficulty_level,
            question_types=self._request.question_types,
            question_count=len(result.questions),
            learning_goal=self._request.learning_goal,
            status="completed",
            prompt_version=GENERATION_PROMPT_VERSION,
        )
        db.add(batch)

        for question_data in result.questions:
            question = GeneratedQuestion(
                id=uuid.uuid4(),
                batch_id=batch.id,
                user_id=user_id,
                knowledge_node_id=question_data.get("knowledge_node_id"),
                subject_code=self._request.subject_code,
                course_topic=self._request.course_topic,
                difficulty_level=question_data.get(
                    "difficulty", self._request.difficulty_level
                ),
                question_type=question_data.get(
                    "question_type", self._request.question_types[0]
                ),
                question_body=question_data["question_body"],
                options=question_data.get("options"),
                correct_answer=question_data["correct_answer"],
                explanation=question_data["explanation"],
                knowledge_tags=question_data.get(
                    "knowledge_tags", question_data.get("tags", [])
                ),
                source_prompt=(
                    f"{GENERATION_PROMPT_VERSION}:"
                    f"{self._request.subject_code}:{self._request.course_topic}"
                ),
                similarity_hash=self.compute_similarity_hash(
                    question_data["question_body"]
                ),
                quality_status="passed",
            )
            db.add(question)
            db.add(
                QuestionQualityCheck(
                    id=uuid.uuid4(),
                    generated_question_id=question.id,
                    check_type="review",
                    status="passed",
                    score=1.0,
                    message=result.review.revision_notes or "审题通过",
                    checker_version=REVIEW_PROMPT_VERSION,
                )
            )

        await db.flush()
        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "[QuestionSaveTool] 批次保存完成: batch=%s | saved=%s | latency=%sms",
            batch.id,
            len(result.questions),
            latency_ms,
        )
        return batch

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
