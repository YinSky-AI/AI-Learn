"""
backend/app/ai/agents/question_planner.py

Layer2 QuestionPlannerAgent —— 出题规划模块

本模块根据课程意图参数和系统反馈控制信号，制定具体的出题方案，
包括题型分布、数量分配和难度配比，为题目生成提供明确的执行计划。

核心职责：
1. 解析 IntentParams 和 ControlSignal
2. 规划题型分布与数量分配
3. 根据 PID 调整建议动态修正难度和数量
4. 检测规划偏差并声明

层级位置：L2
输入：IntentParams (L1) + ControlSignal (L7)
输出：PlanResult（plan_id, question_plan, adjusted_params, deviation_declaration）
接口契约：PlanResult -> QuestionGeneratorAgent (L4)

规划规则：
- 题目总数接近请求数量（±20% 容差）
- 难度分布遵循"金字塔原则"：基础题40%，中等题40%，挑战题20%
- 当 ControlSignal 建议调整时，必须在规划中体现并声明偏差
- 提供降级默认规划，确保 LLM 输出异常时系统仍可运行
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.app.ai.agents.base import BaseAgent
from backend.app.ai.prompts.question_planning import build_question_planning_prompt

logger = logging.getLogger(__name__)


class QuestionPlannerAgent(BaseAgent):
    """
    出题规划 Agent

    接收 IntentParams 和 ControlSignal，规划具体的出题方案。
    如果 ControlSignal 建议调整难度/数量，必须在规划中体现。
    如果调整后的参数偏离原始设定值，必须声明偏差。
    """

    agent_name = "QuestionPlannerAgent"
    layer = "L2"
    upstream_agents = ["CourseIntentAgent"]
    downstream_agents = ["QuestionGeneratorAgent"]
    input_signals = ["IntentParams", "ControlSignal"]
    output_signals = ["PlanResult"]
    requires_json_output = True
    model = "deepseek-chat"
    temperature = 0.3

    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """
        构建出题规划 Prompt

        Args:
            input_data: {
                "age_group": str,
                "subject": str,
                "course_topic": str,
                "difficulty": str,
                "question_types": list[str],
                "question_count": int,
                "learning_goal": str,
                "control_signal": dict,  # 来自 FeedbackAggregator
            }
            context: 执行上下文

        Returns:
            消息列表
        """
        return build_question_planning_prompt(
            age_group=input_data.get("age_group", "10-12"),
            subject=input_data.get("subject", "数学"),
            course_topic=input_data.get("course_topic", ""),
            difficulty=input_data.get("difficulty", "medium"),
            question_types=input_data.get("question_types", ["choice", "fill_blank"]),
            question_count=input_data.get("question_count", 10),
            learning_goal=input_data.get("learning_goal", ""),
            control_signal=input_data.get("control_signal"),
        )

    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        解析 LLM 响应为 PlanResult

        Args:
            response: LLM 响应
            input_data: 原始输入
            context: 执行上下文

        Returns:
            PlanResult 字典
        """
        content = response.get("content", "")
        data = self._safe_parse_json(content)

        # 解析题目规划
        question_plan = data.get("question_plan", [])
        if not question_plan:
            # 降级：生成默认规划
            question_plan = self._default_plan(
                question_types=input_data.get("question_types", ["choice"]),
                question_count=input_data.get("question_count", 10),
                difficulty=input_data.get("difficulty", "medium"),
            )

        adjusted_params = data.get("adjusted_params", {})

        # 检查是否需要偏差声明
        deviation_declaration = None
        original_count = input_data.get("question_count", 10)
        planned_count = sum(item.get("count", 0) for item in question_plan)

        if abs(planned_count - original_count) > original_count * 0.2:
            deviation_declaration = self.get_deviation_declaration(
                expected=original_count,
                actual=planned_count,
                deviation_type="count_adjusted",
                reason=f"根据 ControlSignal 和质量反馈调整题目数量",
            )

        plan_result = {
            "plan_id": data.get("plan_id", ""),
            "question_plan": question_plan,
            "adjusted_params": adjusted_params,
            "deviation_declaration": deviation_declaration,
            "original_count": original_count,
            "planned_count": planned_count,
        }

        logger.info(
            f"[QuestionPlannerAgent] 规划完成: "
            f"题型数={len(question_plan)} | "
            f"计划题数={planned_count} | "
            f"偏差={'有' if deviation_declaration else '无'}"
        )

        return plan_result

    def _default_plan(
        self,
        question_types: list[str],
        question_count: int,
        difficulty: str,
    ) -> list[dict[str, Any]]:
        """
        生成默认规划（降级方案）

        Args:
            question_types: 题型列表
            question_count: 题目数量
            difficulty: 难度

        Returns:
            默认规划列表
        """
        plan = []
        remaining = question_count

        for i, q_type in enumerate(question_types):
            if i == len(question_types) - 1:
                count = remaining
            else:
                count = remaining // (len(question_types) - i)
                remaining -= count

            plan.append({
                "type": q_type,
                "count": count,
                "difficulty": difficulty,
                "weight": 1.0,
            })

        return plan
