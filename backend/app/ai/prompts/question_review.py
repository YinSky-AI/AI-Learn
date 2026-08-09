"""两层出题流水线的审题 Prompt。"""

import json
from typing import Any


PROMPT_VERSION = "v1.0.0"


def build_question_review_prompt(
    request: Any,
    questions: list[dict[str, Any]],
    adaptive_context: Any = None,
) -> list[dict[str, str]]:
    """构建批次审题消息，要求模型只返回结构化审核结论。"""
    adaptive_section = ""
    if adaptive_context is not None:
        adaptive_section = f"""
- 目标知识点代码: {adaptive_context.target_knowledge_point_code}
- 目标错因代码: {adaptive_context.target_misconception_code or '无特定错因'}
- 父题 ID: {adaptive_context.parent_question_id}
- 策略版本: {adaptive_context.policy_version}
若题目没有实际考查目标知识点，或无法暴露指定错误模式，必须返回 passed=false，
并在 revision_notes 中给出围绕目标约束的可执行修订意见。
"""

    system_prompt = f"""你是一位教育题目审核专家。请审核以下题目是否满足出题条件。

## 版本: {PROMPT_VERSION}
- 年龄分级: {request.age_group_code}
- 学科: {request.subject_code}
- 课程主题: {request.course_topic}
- 难度: {request.difficulty_level}
- 题型: {', '.join(request.question_types)}
- 题目数量: {request.question_count}
{adaptive_section}

请核查答案正确性、题干清晰度、选项合理性、适龄性和与主题的一致性。
只返回 JSON 对象，不要使用 Markdown：
{{
  "passed": true,
  "revision_notes": "未通过时给出可执行的中文修订意见；通过时为空字符串"
}}

待审核题目：
{json.dumps(questions, ensure_ascii=False)}
"""
    return [{"role": "system", "content": system_prompt}]
