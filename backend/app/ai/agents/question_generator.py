"""
Layer4 QuestionGeneratorAgent — 题目生成

职责：生成题目、选项、答案、解析
层级位置：L4
输入：PlanResult (L2) + MemoryContext (L3) + ControlSignal (L7)
输出：GeneratedQuestions（questions, generation_meta, deviation_declaration）
接口契约：GeneratedQuestions -> QualityCheckAgent (L5)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.app.ai.agents.base import BaseAgent
from backend.app.ai.prompts.question_generation import build_question_generation_prompt

logger = logging.getLogger(__name__)


class QuestionGeneratorAgent(BaseAgent):
    """
    题目生成 Agent

    根据规划和记忆上下文，生成高质量的题目。
    接收 ControlSignal 调整生成策略。
    如果生成题目的实际难度与规划不一致，必须声明偏差。
    """

    agent_name = "QuestionGeneratorAgent"
    layer = "L4"
    upstream_agents = ["QuestionPlannerAgent", "QuestionMemoryAgent"]
    downstream_agents = ["QualityCheckAgent"]
    input_signals = ["PlanResult", "MemoryContext", "ControlSignal"]
    output_signals = ["GeneratedQuestions"]
    requires_json_output = True
    model = "deepseek-chat"  # DeepSeek 主模型确保生成质量
    temperature = 0.7
    max_tokens = 8192  # 生成多道题需要更多 Token

    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """
        构建题目生成 Prompt

        Args:
            input_data: {
                "age_group": str,
                "subject": str,
                "course_topic": str,
                "difficulty": str,
                "question_type": str,
                "question_count": int,
                "avoid_list": list,
                "skill_hints": list,
                "error_patterns": list,
                "coverage_gaps": list,
                "control_signal": dict,
            }
            context: 执行上下文

        Returns:
            消息列表
        """
        return build_question_generation_prompt(
            age_group=input_data.get("age_group", "10-12"),
            subject=input_data.get("subject", "数学"),
            course_topic=input_data.get("course_topic", ""),
            difficulty=input_data.get("difficulty", "medium"),
            question_type=input_data.get("question_type", "choice"),
            question_count=input_data.get("question_count", 5),
            avoid_list=input_data.get("avoid_list"),
            skill_hints=input_data.get("skill_hints"),
            error_patterns=input_data.get("error_patterns"),
            coverage_gaps=input_data.get("coverage_gaps"),
            control_signal=input_data.get("control_signal"),
        )

    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        解析 LLM 响应为 GeneratedQuestions

        Args:
            response: LLM 响应
            input_data: 原始输入
            context: 执行上下文

        Returns:
            GeneratedQuestions 字典
        """
        content = response.get("content", "")

        try:
            data = self._safe_parse_json(content)
        except Exception:
            logger.error("[QuestionGeneratorAgent] JSON 解析失败，返回空列表")
            return {
                "questions": [],
                "generation_meta": self._build_meta(response, input_data),
                "deviation_declaration": self.get_deviation_declaration(
                    expected="JSON array",
                    actual="unparseable text",
                    deviation_type="parse_failure",
                    reason="LLM 输出无法解析为 JSON",
                ),
            }

        # data 可能是单个对象或数组
        if isinstance(data, dict):
            questions_raw = data.get("questions", [data])
        elif isinstance(data, list):
            questions_raw = data
        else:
            questions_raw = []

        # 规范化每道题目
        questions = []
        for q in questions_raw:
            if not isinstance(q, dict):
                continue
            if not q.get("question_body") or not q.get("correct_answer"):
                continue

            question = {
                "id": q.get("id", ""),
                "question_type": q.get("question_type", input_data.get("question_type", "choice")),
                "question_body": q.get("question_body", ""),
                "options": q.get("options"),
                "correct_answer": str(q.get("correct_answer", "")),
                "explanation": q.get("explanation", ""),
                "tags": q.get("tags", []),
                "difficulty": q.get("difficulty", input_data.get("difficulty", "medium")),
                "similarity_hash": q.get("similarity_hash", ""),
            }
            questions.append(question)

        # 检查偏差（实际难度 vs 规划难度）
        deviation_declaration = None
        planned_difficulty = input_data.get("difficulty", "medium")
        actual_difficulties = [q["difficulty"] for q in questions if q.get("difficulty")]

        if actual_difficulties:
            # 检查是否有难度漂移
            off_target = sum(
                1 for d in actual_difficulties if d != planned_difficulty
            )
            if off_target > len(actual_difficulties) * 0.5:
                # 超过半数题目难度不一致
                most_common = max(
                    set(actual_difficulties),
                    key=actual_difficulties.count,
                )
                deviation_declaration = self.get_deviation_declaration(
                    expected=planned_difficulty,
                    actual=most_common,
                    deviation_type="difficulty_mismatch",
                    reason=f"超过半数题目实际难度为 {most_common}，与规划难度 {planned_difficulty} 不一致",
                )

        result = {
            "questions": questions,
            "generation_meta": self._build_meta(response, input_data),
            "deviation_declaration": deviation_declaration,
        }

        logger.info(
            f"[QuestionGeneratorAgent] 生成完成: "
            f"题目数={len(questions)} | "
            f"偏差={'有' if deviation_declaration else '无'}"
        )

        return result

    def _build_meta(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """构建生成元信息"""
        usage = response.get("usage", {})
        return {
            "model_name": response.get("model", self.model),
            "prompt_version": "v0.1.0",
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": response.get("latency_ms", 0),
        }
