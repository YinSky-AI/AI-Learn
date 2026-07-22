"""两层出题流水线的审题 Prompt。"""

import json
from typing import Any


PROMPT_VERSION = "v1.0.0"


def build_question_review_prompt(request: Any, questions: list[dict[str, Any]]) -> list[dict[str, str]]:
    """构建批次审题消息，要求模型只返回结构化审核结论。"""
    system_prompt = f"""你是一位教育题目审核专家。请审核以下题目是否满足出题条件。

## 版本: {PROMPT_VERSION}
- 年龄分级: {request.age_group_code}
- 学科: {request.subject_code}
- 课程主题: {request.course_topic}
- 难度: {request.difficulty_level}
- 题型: {', '.join(request.question_types)}
- 题目数量: {request.question_count}

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
