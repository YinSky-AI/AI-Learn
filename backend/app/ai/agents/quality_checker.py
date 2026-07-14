"""
backend/app/ai/agents/quality_checker.py

Layer5 QualityCheckAgent —— 快速质量检查模块

本模块对每道生成题目执行四维快速检查，是质量闭环的关键环节。
每道题必检、不遗漏，未通过题目将被过滤并触发 FeedbackAggregator 的纠正信号。

检查维度与权重：
1. 答案正确性（权重40%）
2. 适龄性（权重25%）
3. 难度匹配（权重20%）
4. 重复度（权重15%）

层级位置：L5
输入：GeneratedQuestions (L4)
输出：QuickCheckResult（question_id, passed, score, issues, deviation）
接口契约：QuickCheckResult -> FeedbackAggregator (L7)

设计特点：
- 使用极低 temperature（0.1）确保检查结果稳定一致
- 服务端强制阈值校验（QUALITY_PASS_THRESHOLD = 60），防止 LLM 误判
- JSON 解析失败时默认不通过，保守策略确保质量
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.app.ai.agents.base import BaseAgent
from backend.app.ai.prompts.quality_check import build_quality_check_prompt

logger = logging.getLogger(__name__)

# 质量通过阈值
QUALITY_PASS_THRESHOLD = 60.0


class QualityCheckAgent(BaseAgent):
    """
    快速质量检查 Agent

    对每道生成题目执行四维快检：
    1. 答案正确性（权重40%）
    2. 适龄性（权重25%）
    3. 难度匹配（权重20%）
    4. 重复度（权重15%）

    每道题必检，不遗漏。
    """

    agent_name = "QualityCheckAgent"
    layer = "L5"
    upstream_agents = ["QuestionGeneratorAgent"]
    downstream_agents = ["FeedbackAggregator"]
    input_signals = ["GeneratedQuestions"]
    output_signals = ["QuickCheckResult"]
    requires_json_output = True
    model = "deepseek-chat"
    temperature = 0.1  # 极低温度，确保检查结果稳定
    max_tokens = 2048

    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """
        构建质量检查 Prompt

        Args:
            input_data: {
                "question": dict,           # 单道题目
                "age_group": str,
                "subject": str,
                "expected_difficulty": str,
            }
            context: 执行上下文

        Returns:
            消息列表
        """
        question = input_data.get("question", {})
        return build_quality_check_prompt(
            question=question,
            age_group=input_data.get("age_group", "10-12"),
            subject=input_data.get("subject", "数学"),
            expected_difficulty=input_data.get("expected_difficulty", "medium"),
        )

    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        解析 LLM 响应为 QuickCheckResult

        Args:
            response: LLM 响应
            input_data: 原始输入（包含 question）
            context: 执行上下文

        Returns:
            QuickCheckResult 字典
        """
        content = response.get("content", "")
        question = input_data.get("question", {})
        question_id = question.get("id", "unknown")

        try:
            data = self._safe_parse_json(content)
        except Exception:
            # 解析失败，默认不通过
            logger.warning(f"[QualityCheckAgent] 解析失败，默认不通过: qid={question_id}")
            return self._build_fail_result(question_id, "LLM 响应解析失败")

        passed = data.get("passed", False)
        score = float(data.get("score", 0))

        # 解析 issues
        issues = []
        for issue in data.get("issues", []):
            issues.append({
                "dimension": issue.get("dimension", "unknown"),
                "detail": issue.get("detail", ""),
                "severity": issue.get("severity", "warning"),
            })

        # 如果 score 低于阈值，强制不通过
        if score < QUALITY_PASS_THRESHOLD:
            passed = False
            issues.append({
                "dimension": "overall",
                "detail": f"综合得分 {score} 低于阈值 {QUALITY_PASS_THRESHOLD}",
                "severity": "blocking",
            })

        # 计算偏差信号
        expected_score = 80.0  # 期望分数
        deviation_value = expected_score - score  # 正值表示低于期望

        result = {
            "question_id": question_id,
            "passed": passed,
            "score": score,
            "issues": issues,
            "deviation": {
                "type": "quality",
                "value": deviation_value,
            },
        }

        logger.info(
            f"[QualityCheckAgent] 检查完成: qid={question_id} | "
            f"passed={passed} | score={score:.1f} | "
            f"issues={len(issues)}"
        )

        return result

    def _build_fail_result(self, question_id: str, reason: str) -> dict[str, Any]:
        """构建默认失败结果"""
        return {
            "question_id": question_id,
            "passed": False,
            "score": 0.0,
            "issues": [{
                "dimension": "system",
                "detail": reason,
                "severity": "blocking",
            }],
            "deviation": {
                "type": "quality",
                "value": 80.0,
            },
        }
