"""独立的两层 AI 出题与审题流水线。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.ai.prompts.question_generation import build_question_generation_prompt
from app.ai.prompts.question_review import build_question_review_prompt
from app.ai.provider import AIProvider
from app.schemas.question import QuestionGenerateRequest

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


class QuestionGenerationError(Exception):
    """可以安全展示给用户的题目生成错误。"""


@dataclass
class QuestionReviewResult:
    """审题 Agent 的结构化结论。"""

    passed: bool
    revision_notes: str


@dataclass
class GeneratedBatchResult:
    """通过审题的题目批次及其审题结论。"""

    questions: list[dict[str, Any]]
    review: QuestionReviewResult


class QuestionPipeline:
    """只编排出题 Agent 和审题 Agent 的生成流程。"""

    def __init__(self, provider: AIProvider):
        self._provider = provider

    async def generate(
        self,
        request: QuestionGenerateRequest,
        user_id: str,
        db: Any,
    ) -> GeneratedBatchResult:
        """生成题目并立即审题，最多进行三次生成尝试。"""
        del user_id, db
        revision_notes = ""

        for attempt in range(MAX_ATTEMPTS):
            logger.info("两层出题流水线第 %s/%s 次生成", attempt + 1, MAX_ATTEMPTS)
            questions = await self._generate_questions(request, revision_notes)
            review = await self._review_questions(request, questions)
            if review.passed:
                logger.info("两层出题流水线审题通过")
                return GeneratedBatchResult(questions=questions, review=review)

            revision_notes = review.revision_notes
            logger.warning("两层出题流水线审题未通过，准备按意见修订")

        raise QuestionGenerationError("题目未能通过审核，请调整条件后重试")

    async def _generate_questions(
        self,
        request: QuestionGenerateRequest,
        revision_notes: str,
    ) -> list[dict[str, Any]]:
        messages = build_question_generation_prompt(
            age_group=request.age_group_code,
            subject=request.subject_code,
            course_topic=request.course_topic,
            difficulty=request.difficulty_level,
            question_type=request.question_types[0],
            question_count=request.question_count,
            revision_notes=revision_notes,
        )
        response = await self._provider.generate(messages)
        parsed = self._parse_response(response, "题目生成结果格式无效，请稍后重试")
        if not isinstance(parsed, list):
            raise QuestionGenerationError("题目生成结果格式无效，请稍后重试")
        return parsed

    async def _review_questions(
        self,
        request: QuestionGenerateRequest,
        questions: list[dict[str, Any]],
    ) -> QuestionReviewResult:
        response = await self._provider.generate(build_question_review_prompt(request, questions))
        parsed = self._parse_response(response, "题目审核结果格式无效，请稍后重试")
        if not isinstance(parsed, dict) or not isinstance(parsed.get("passed"), bool):
            raise QuestionGenerationError("题目审核结果格式无效，请稍后重试")
        return QuestionReviewResult(
            passed=parsed["passed"],
            revision_notes=str(parsed.get("revision_notes", "")),
        )

    @staticmethod
    def _parse_response(response: dict[str, Any], user_error: str) -> Any:
        content = response.get("content", "")
        if not isinstance(content, str):
            raise QuestionGenerationError(user_error)
        normalized = content.strip()
        if normalized.startswith("```") and normalized.endswith("```"):
            normalized = normalized.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(normalized)
        except json.JSONDecodeError as error:
            logger.error("两层出题流水线收到无效 JSON: %s", error)
            raise QuestionGenerationError(user_error) from error
