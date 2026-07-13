"""
Layer6 SafetyAuditAgent — 四维安全审查

职责：四维安全审查（适龄性/准确性/公平性/隐私），一票否决权
层级位置：L6（深审层）
输入：QualityCheckAgent 通过的题目
输出：SafetyAuditResult（verdict, scores, issues, blocking_issue）
接口契约：SafetyAuditResult -> FeedbackAggregator (L7) + ErrorLogger

关键约束：
- 任一维度低于 6 分，整道题目一票否决
- 否决的题目不进入生成题目知识库
- 不得修改被审查的题目，只做 PASS/REJECT 判定
- 安全审查在 QualityCheckAgent 之后执行
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.app.ai.agents.base import BaseAgent
from backend.app.ai.prompts.safety_audit import build_safety_audit_prompt, SAFETY_THRESHOLD

logger = logging.getLogger(__name__)


class SafetyAuditAgent(BaseAgent):
    """
    安全审查 Agent

    独立于生成流水线，具有一票否决权。
    四维审查：内容适龄性、信息准确性、公平性与包容性、隐私安全。
    """

    agent_name = "SafetyAuditAgent"
    layer = "L6"
    upstream_agents = ["QualityCheckAgent"]
    downstream_agents = ["FeedbackAggregator", "ErrorLogger"]
    input_signals = ["GeneratedQuestions"]
    output_signals = ["SafetyAuditResult"]
    requires_json_output = True
    model = "deepseek-chat"
    temperature = 0.1  # 极低温度，确保审查一致性
    max_tokens = 2048

    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """
        构建安全审查 Prompt

        Args:
            input_data: {
                "question": dict,
                "age_group": str,
                "subject": str,
            }
            context: 执行上下文

        Returns:
            消息列表
        """
        question = input_data.get("question", {})
        return build_safety_audit_prompt(
            question=question,
            age_group=input_data.get("age_group", "10-12"),
            subject=input_data.get("subject", "数学"),
        )

    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        解析 LLM 响应为 SafetyAuditResult

        Args:
            response: LLM 响应
            input_data: 原始输入
            context: 执行上下文

        Returns:
            SafetyAuditResult 字典
        """
        content = response.get("content", "")
        question = input_data.get("question", {})
        question_id = question.get("id", "unknown")

        try:
            data = self._safe_parse_json(content)
        except Exception:
            # 解析失败，默认否决（安全优先原则）
            logger.warning(f"[SafetyAuditAgent] 解析失败，默认否决: qid={question_id}")
            return self._build_reject_result(
                question_id, "安全审查 LLM 响应解析失败"
            )

        scores = data.get("scores", {})
        verdict_str = data.get("verdict", "PASS").upper()

        # 提取四维评分
        age_score = float(scores.get("age_appropriate", 10))
        accuracy_score = float(scores.get("accuracy", 10))
        fairness_score = float(scores.get("fairness", 10))
        privacy_score = float(scores.get("privacy", 10))

        # 强制检查阈值（即使 LLM 判定 PASS，也要验证）
        min_score = min(age_score, accuracy_score, fairness_score, privacy_score)
        if min_score < SAFETY_THRESHOLD:
            verdict_str = "REJECT"
            logger.warning(
                f"[SafetyAuditAgent] 阈值否决: qid={question_id} | "
                f"min_score={min_score:.1f} < threshold={SAFETY_THRESHOLD}"
            )

        verdict = "PASS" if verdict_str == "PASS" else "REJECT"

        # 解析 issues
        issues = []
        for issue in data.get("issues", []):
            issues.append({
                "dimension": issue.get("dimension", "unknown"),
                "detail": issue.get("detail", ""),
                "severity": issue.get("severity", "warning"),
            })

        # 否决原因
        blocking_issue = data.get("blocking_issue")
        if verdict == "REJECT" and not blocking_issue:
            # 自动生成否决原因
            low_dims = []
            if age_score < SAFETY_THRESHOLD:
                low_dims.append(f"适龄性({age_score:.0f}分)")
            if accuracy_score < SAFETY_THRESHOLD:
                low_dims.append(f"准确性({accuracy_score:.0f}分)")
            if fairness_score < SAFETY_THRESHOLD:
                low_dims.append(f"公平性({fairness_score:.0f}分)")
            if privacy_score < SAFETY_THRESHOLD:
                low_dims.append(f"隐私({privacy_score:.0f}分)")
            blocking_issue = f"安全审查未通过：{', '.join(low_dims)}"

        result = {
            "question_id": question_id,
            "verdict": verdict,
            "scores": {
                "age_appropriate": age_score,
                "accuracy": accuracy_score,
                "fairness": fairness_score,
                "privacy": privacy_score,
            },
            "issues": issues,
            "blocking_issue": blocking_issue,
        }

        logger.info(
            f"[SafetyAuditAgent] 审查完成: qid={question_id} | "
            f"verdict={verdict} | "
            f"scores=[{age_score:.0f},{accuracy_score:.0f},{fairness_score:.0f},{privacy_score:.0f}]"
        )

        return result

    def _build_reject_result(
        self, question_id: str, reason: str
    ) -> dict[str, Any]:
        """构建默认否决结果"""
        return {
            "question_id": question_id,
            "verdict": "REJECT",
            "scores": {
                "age_appropriate": 0.0,
                "accuracy": 0.0,
                "fairness": 0.0,
                "privacy": 0.0,
            },
            "issues": [{
                "dimension": "system",
                "detail": reason,
                "severity": "blocking",
            }],
            "blocking_issue": reason,
        }
