"""
Layer1 CourseIntentAgent — 课程意图理解

职责：理解用户课程选择，补齐结构化参数
层级位置：L1（闭环入口）
输入：用户原始输入 + 可选的已知参数（年龄、学科）
输出：IntentParams（age_group, subject, course_topic, difficulty, question_types, question_count, learning_goal）
接口契约：IntentParams -> QuestionPlannerAgent (L2)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.app.ai.agents.base import BaseAgent
from backend.app.ai.prompts.course_intent import build_course_intent_prompt

logger = logging.getLogger(__name__)


class CourseIntentAgent(BaseAgent):
    """
    课程意图理解 Agent

    接收用户自然语言输入，输出结构化的课程意图参数。
    使用 DeepSeek 模型即可完成。
    """

    agent_name = "CourseIntentAgent"
    layer = "L1"
    upstream_agents = []
    downstream_agents = ["QuestionPlannerAgent"]
    input_signals = ["user_input"]
    output_signals = ["IntentParams"]
    requires_json_output = True
    model = "deepseek-chat"
    temperature = 0.3  # 低温度，确保输出稳定

    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """
        构建课程意图理解 Prompt

        Args:
            input_data: {
                "user_input": str,        # 用户原始输入
                "age_group": str,          # 已知年龄分级（可选）
                "subject": str,            # 已知学科（可选）
            }
            context: 执行上下文

        Returns:
            消息列表
        """
        user_input = input_data.get("user_input", "")
        age_group = input_data.get("age_group", "")
        subject = input_data.get("subject", "")

        return build_course_intent_prompt(
            user_input=user_input,
            age_group=age_group,
            subject=subject,
        )

    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        解析 LLM 响应为 IntentParams

        Args:
            response: LLM 响应
            input_data: 原始输入
            context: 执行上下文

        Returns:
            IntentParams 字典
        """
        content = response.get("content", "")
        data = self._safe_parse_json(content)

        # 验证必填字段
        required_fields = ["age_group", "subject", "course_topic", "difficulty"]
        missing_fields = [f for f in required_fields if f not in data or not data[f]]
        if missing_fields:
            raise ValueError(f"IntentParams 缺少必填字段: {missing_fields}")

        # 规范化输出
        intent_params = {
            "age_group": str(data["age_group"]).strip(),
            "subject": str(data["subject"]).strip(),
            "course_topic": str(data["course_topic"]).strip(),
            "difficulty": str(data["difficulty"]).strip().lower(),
            "question_types": data.get("question_types", ["choice", "fill_blank"]),
            "question_count": max(1, min(50, int(data.get("question_count", 10)))),
            "learning_goal": data.get("learning_goal", ""),
            "raw_input": input_data.get("user_input", ""),
            "clarification_required": data.get("clarification_required", False),
        }

        # 验证 difficulty 值
        valid_difficulties = {"easy", "medium", "hard"}
        if intent_params["difficulty"] not in valid_difficulties:
            logger.warning(
                f"无效难度值 '{intent_params['difficulty']}'，使用默认值 'medium'"
            )
            intent_params["difficulty"] = "medium"

        logger.info(
            f"[CourseIntentAgent] 意图解析完成: "
            f"subject={intent_params['subject']} | "
            f"topic={intent_params['course_topic']} | "
            f"difficulty={intent_params['difficulty']} | "
            f"count={intent_params['question_count']}"
        )

        return intent_params
