"""
Layer6 QualityReviewAgent — 深度质量评估 + 趋势分析

职责：抽样深度质量评估 + 趋势分析 + 系统性反馈
层级位置：L6（深审层，与 SafetyAuditAgent 并行）
输入：批量质量检查数据
输出：QualityTrendReport（trend, system_score, top_issues, agent_feedback, recommended_adjustments）
接口契约：QualityTrendReport -> FeedbackAggregator (L7)

关键约束：
- 与 QualityCheckAgent 互补，不是替代关系
- 每批次随机抽取 20% 的题目进行深度审查
- QC 边缘区间（60-70分）的题目 100% 审查
- 不得直接修改题目，只做评估和建议
- 趋势报告包含推荐调整参数
"""

from __future__ import annotations

import logging
import random
from typing import Any, Optional

from backend.app.ai.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class QualityReviewAgent(BaseAgent):
    """
    深度质量评估 Agent

    独立于 QualityCheckAgent 的深度评估，六维评估体系：
    1. 知识点准确性
    2. 难度匹配度
    3. 选项区分度
    4. 解析质量
    5. 语言规范性
    6. 适龄性复核

    可异步执行，不阻塞生成流程。
    """

    agent_name = "QualityReviewAgent"
    layer = "L6"
    upstream_agents = ["QualityCheckAgent"]
    downstream_agents = ["FeedbackAggregator"]
    input_signals = ["QuickCheckResult"]
    output_signals = ["QualityTrendReport"]
    requires_json_output = True
    model = "deepseek-chat"
    temperature = 0.2
    max_tokens = 4096

    # 默认抽样率
    DEFAULT_SAMPLE_RATE = 0.2
    # 边缘区间
    EDGE_SCORE_MIN = 60.0
    EDGE_SCORE_MAX = 70.0

    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """
        构建深度质量评估 Prompt

        Args:
            input_data: {
                "sampled_questions": list,     # 抽样题目
                "quality_checks": list,         # QC 结果
                "historical_scores": list,      # 历史质量分数
                "subject": str,
                "age_group": str,
            }
            context: 执行上下文

        Returns:
            消息列表
        """
        sampled = input_data.get("sampled_questions", [])
        qc_results = input_data.get("quality_checks", [])
        historical = input_data.get("historical_scores", [])
        subject = input_data.get("subject", "数学")

        system_prompt = f"""你是一位教育质量评估专家。请对以下抽样题目进行六维深度质量评估。

## 版本: v0.1.0

## 六维评估体系
1. **知识点准确性**: 题目所涉知识是否正确
2. **难度匹配度**: 实际难度是否与标注一致
3. **选项区分度**: 错误选项是否有合理的干扰性
4. **解析质量**: 解析是否清晰、准确、有教育价值
5. **语言规范性**: 语言是否流畅、无歧义、符合中文表达习惯
6. **适龄性复核**: 对 SafetyAuditAgent 的适龄性判断进行二次复核

## 抽样题目（{len(sampled)} 道）
```json
{sampled[:10]}
```

## 质量快检结果
```json
{qc_results[:10]}
```

## 历史质量趋势（最近批次）
```json
{historical[-10:]}
```

## 输出格式
请以 JSON 格式输出：
{{
    "trend": "improving / stable / declining",
    "system_quality_score": 0-100,
    "top_issues": [
        {{
            "type": "问题类型",
            "frequency": "频率",
            "suggestion": "改进建议"
        }}
    ],
    "agent_feedback": {{
        "QuestionGeneratorAgent": {{
            "strength": "优势",
            "weakness": "不足"
        }},
        "QualityCheckAgent": {{
            "missed_issues": "遗漏问题"
        }}
    }},
    "recommended_adjustments": {{
        "difficulty_delta": -1到1,
        "quality_threshold_adjustment": 0-10
    }}
}}
"""

        return [{"role": "system", "content": system_prompt}]

    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        解析 LLM 响应为 QualityTrendReport

        Args:
            response: LLM 响应
            input_data: 原始输入
            context: 执行上下文

        Returns:
            QualityTrendReport 字典
        """
        content = response.get("content", "")

        try:
            data = self._safe_parse_json(content)
        except Exception:
            logger.warning("[QualityReviewAgent] 解析失败，返回默认趋势报告")
            return self._default_trend_report()

        trend = data.get("trend", "stable")
        # 验证 trend 值
        if trend not in ("improving", "stable", "declining"):
            trend = "stable"

        result = {
            "batch_id": data.get("batch_id", ""),
            "trend": trend,
            "system_quality_score": float(data.get("system_quality_score", 0)),
            "top_issues": data.get("top_issues", []),
            "agent_feedback": data.get("agent_feedback", {}),
            "recommended_adjustments": data.get("recommended_adjustments", {}),
        }

        logger.info(
            f"[QualityReviewAgent] 趋势分析完成: "
            f"trend={trend} | "
            f"system_score={result['system_quality_score']:.1f} | "
            f"top_issues={len(result['top_issues'])}"
        )

        return result

    def select_samples(
        self,
        questions: list[dict],
        qc_results: list[dict],
        sample_rate: float = DEFAULT_SAMPLE_RATE,
    ) -> list[dict]:
        """
        选择抽样题目

        策略：
        1. 随机抽取 20% 的题目
        2. QC 边缘区间（60-70分）的题目 100% 审查

        Args:
            questions: 全部题目列表
            qc_results: QC 结果列表
            sample_rate: 抽样率

        Returns:
            抽样题目列表
        """
        if not questions:
            return []

        # 构建 QC 分数映射
        qc_score_map = {}
        for qc in qc_results:
            qid = qc.get("question_id", "")
            qc_score_map[qid] = qc.get("score", 100)

        selected = set()

        # 策略1: 边缘区间 100% 审查
        for q in questions:
            qid = q.get("id", "")
            score = qc_score_map.get(qid, 100)
            if self.EDGE_SCORE_MIN <= score <= self.EDGE_SCORE_MAX:
                selected.add(id(q))

        # 策略2: 随机抽样
        non_edge = [q for q in questions if id(q) not in selected]
        sample_size = max(1, int(len(questions) * sample_rate) - len(selected))
        if non_edge and sample_size > 0:
            random.seed(42)  # 固定种子确保可复现
            sampled = random.sample(non_edge, min(sample_size, len(non_edge)))
            for q in sampled:
                selected.add(id(q))

        return [q for q in questions if id(q) in selected]

    def _default_trend_report(self) -> dict[str, Any]:
        """构建默认趋势报告（降级方案）"""
        return {
            "batch_id": "",
            "trend": "stable",
            "system_quality_score": 0.0,
            "top_issues": [],
            "agent_feedback": {},
            "recommended_adjustments": {},
        }
