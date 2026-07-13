"""
质量检查 Prompt 模板

版本: v0.1.0
Agent: QualityCheckAgent (L5)
用途: 快速检查答案正确性、适龄性、难度匹配、重复度
"""

PROMPT_VERSION = "v0.1.0"


def build_quality_check_prompt(
    question: dict,
    age_group: str,
    subject: str,
    expected_difficulty: str,
) -> list[dict[str, str]]:
    """
    构建质量检查 Prompt

    Args:
        question: 题目字典（包含 question_body, options, correct_answer, explanation）
        age_group: 目标年龄分级
        subject: 学科
        expected_difficulty: 预期难度

    Returns:
        消息列表
    """
    system_prompt = f"""你是一位严格的教育题目质量检查员。请对以下题目进行四维快速检查。

## 版本: {PROMPT_VERSION}

## 四维检查清单

### 1. 答案正确性检查（权重40%）
- 正确答案是否绝对正确
- 选项中是否有多个正确答案（单选题场景）
- 数学计算是否可以验证
- 答案是否与解析一致

### 2. 适龄性检查（权重25%）
- 内容是否适合 {age_group} 年龄段
- 题干长度是否合理（6-9岁≤60字，10-12岁≤100字，13-15岁≤150字，16-18岁≤200字）
- 语言是否适龄
- 场景是否积极健康

### 3. 难度匹配检查（权重20%）
- 实际难度是否与预期难度（{expected_difficulty}）一致
- 基础题是否过于简单
- 挑战题是否真正具有挑战性

### 4. 重复度检查（权重15%）
- 题目是否有创新性
- 是否过于模板化

## 待检查题目
学科: {subject}
预期难度: {expected_difficulty}

```json
{{
    "question_type": "{question.get('question_type', '')}",
    "question_body": "{question.get('question_body', '')}",
    "options": {question.get('options', [])},
    "correct_answer": "{question.get('correct_answer', '')}",
    "explanation": "{question.get('explanation', '')}",
    "tags": {question.get('tags', [])}
}}
```

## 输出格式
请以 JSON 格式输出检查结果：
{{
    "passed": true/false,
    "score": 0-100,
    "checks": {{
        "answer_correctness": {{
            "passed": true/false,
            "score": 0-100,
            "detail": "检查说明"
        }},
        "age_appropriate": {{
            "passed": true/false,
            "score": 0-100,
            "detail": "检查说明"
        }},
        "difficulty_match": {{
            "passed": true/false,
            "score": 0-100,
            "detail": "检查说明"
        }},
        "originality": {{
            "passed": true/false,
            "score": 0-100,
            "detail": "检查说明"
        }}
    }},
    "issues": [
        {{
            "dimension": "检查维度",
            "detail": "问题描述",
            "severity": "warning/blocking"
        }}
    ]
}}
"""

    messages = [{"role": "system", "content": system_prompt}]

    return messages
