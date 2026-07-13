"""
Layer3 QuestionMemoryAgent — 记忆检索

职责：检索生成题目知识库、历史题、错题、用户偏好，去重上下文
层级位置：L3
输入：PlanResult (L2) + ControlSignal (L7)
输出：MemoryContext（avoid_list, recent_feedback, user_preferences, skill_hints）
接口契约：MemoryContext -> QuestionGeneratorAgent (L4)

v0.1 约束：
- 生成题目知识库是"历史生成题 + 用户答题记录 + 题目标签 + 题目指纹"的长期沉淀
- 使用 PostgreSQL tsvector + pg_trgm 做相似题检索
- 不实现联网搜索
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.app.ai.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class QuestionMemoryAgent(BaseAgent):
    """
    记忆检索 Agent

    检索生成题目知识库中的历史生成题、错题、用户偏好，
    形成去重上下文和策略提示。

    注意：此 Agent 的 LLM 调用主要用于对检索结果做智能筛选和排序，
    实际的数据库检索通过 QuestionMemoryTool 完成。
    """

    agent_name = "QuestionMemoryAgent"
    layer = "L3"
    upstream_agents = ["QuestionPlannerAgent"]
    downstream_agents = ["QuestionGeneratorAgent"]
    input_signals = ["PlanResult", "ControlSignal"]
    output_signals = ["MemoryContext"]
    requires_json_output = True
    model = "deepseek-chat"
    temperature = 0.3

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 记忆工具的回调函数（由 Harness 注入）
        self._memory_search_callback: Optional[Any] = None
        self._skill_search_callback: Optional[Any] = None

    def set_memory_search_callback(self, callback: Any) -> None:
        """设置记忆检索回调"""
        self._memory_search_callback = callback

    def set_skill_search_callback(self, callback: Any) -> None:
        """设置 Skill 检索回调"""
        self._skill_search_callback = callback

    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """
        构建记忆筛选 Prompt

        对检索到的历史题目做智能筛选，判断哪些需要避免。

        Args:
            input_data: {
                "subject": str,
                "course_topic": str,
                "difficulty": str,
                "retrieved_questions": list,   # 从数据库检索到的题目
                "user_preferences": dict,        # 用户偏好
                "error_patterns": list,          # 错误模式
                "skill_hints": list,             # Skill 提示
                "control_signal": dict,          # ControlSignal
            }
            context: 执行上下文

        Returns:
            消息列表
        """
        retrieved = input_data.get("retrieved_questions", [])
        subject = input_data.get("subject", "数学")
        topic = input_data.get("course_topic", "")
        control_signal = input_data.get("control_signal")

        # 控制信号段落
        control_section = ""
        if control_signal:
            state = control_signal.get("state_estimate", {})
            control_section = f"""
## 控制信号
- 重复风险: {state.get('duplicate_risk', 0.0)}
- 知识覆盖度: {state.get('coverage', 0.0)}
"""

        system_prompt = f"""你是一位教育题目去重专家。请从检索到的历史题目中筛选出需要避免的重复题目。

## 版本: v0.1.0

## 任务
从以下历史题目中，识别与 "{topic}"（{subject}）高度相似的题目，生成去重列表。

## 历史题目列表
共 {len(retrieved)} 道历史题目：
```json
{retrieved[:20]}
```
{control_section}

## 输出格式
请以 JSON 格式输出：
{{
    "avoid_list": [
        {{
            "id": "题目ID",
            "similarity_hash": "指纹",
            "question_body_preview": "题干预览",
            "similarity_score": 0.0-1.0
        }}
    ],
    "coverage_gaps": ["知识点覆盖缺口"],
    "reasoning": "筛选理由"
}}

## 筛选标准
- similarity_score > 0.7 的题目必须加入 avoid_list
- 同一知识点的题目不超过 3 道进入 avoid_list
- 优先保留高质量、高用户评价的题目
"""

        return [{"role": "system", "content": system_prompt}]

    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        解析 LLM 响应为 MemoryContext

        Args:
            response: LLM 响应
            input_data: 原始输入
            context: 执行上下文

        Returns:
            MemoryContext 字典
        """
        content = response.get("content", "")

        try:
            data = self._safe_parse_json(content)
        except Exception:
            # LLM 解析失败，使用原始检索结果
            data = {
                "avoid_list": [],
                "coverage_gaps": [],
                "reasoning": "LLM 解析失败，使用默认值",
            }

        # 组装 MemoryContext
        memory_context = {
            "avoid_list": data.get("avoid_list", []),
            "recent_feedback": input_data.get("recent_feedback", []),
            "user_preferences": input_data.get("user_preferences", {}),
            "skill_hints": input_data.get("skill_hints", []),
            "error_patterns": input_data.get("error_patterns", []),
            "coverage_gaps": data.get("coverage_gaps", []),
        }

        logger.info(
            f"[QuestionMemoryAgent] 记忆检索完成: "
            f"avoid_count={len(memory_context['avoid_list'])} | "
            f"skill_hints={len(memory_context['skill_hints'])} | "
            f"gaps={len(memory_context['coverage_gaps'])}"
        )

        return memory_context
