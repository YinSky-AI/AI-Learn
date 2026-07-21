"""
backend/app/ai/prompts/question_generation.py

出题 Prompt 模板

本模板用于 L4 QuestionGeneratorAgent，根据规划参数和记忆上下文生成高质量教育题目。
模板按年龄段定义差异化的适龄性要求，确保生成内容符合认知发展水平。

版本: v0.1.0
Agent: QuestionGeneratorAgent (L4)
用途: 生成题目、选项、答案、解析

适龄性要求覆盖：
- 6-9 岁：简单易懂，生活化场景，题干 ≤60 字
- 10-12 岁：适当增加专业术语，题干 ≤100 字
- 13-15 岁：可使用学科专业术语，题干 ≤150 字
- 16-18 岁：接近成人表达，可包含抽象概念，题干 ≤200 字

注入信息：
- 避免列表（去重）
- Skill 策略提示
- 已知错误模式
- 知识覆盖缺口
- 控制信号（动态调整）
"""

PROMPT_VERSION = "v0.1.0"

# 各年龄段的适龄性要求
AGE_REQUIREMENTS = {
    "6-9": {
        "max_question_length": 60,
        "max_option_length": 20,
        "language_level": "简单易懂，使用生活化场景",
        "scenario_examples": "分水果、分蛋糕、数动物、买东西",
        "avoid": "暴力、恐怖、复杂社会议题、抽象概念",
    },
    "10-12": {
        "max_question_length": 100,
        "max_option_length": 30,
        "language_level": "适当增加专业术语，但保持生活化",
        "scenario_examples": "购物折扣、旅行计算、实验观察、阅读理解",
        "avoid": "暴力、恐怖、政治敏感、成人文案",
    },
    "13-15": {
        "max_question_length": 150,
        "max_option_length": 40,
        "language_level": "可以使用学科专业术语",
        "scenario_examples": "科学实验、社会调查、数据分析",
        "avoid": "暴力、恐怖、政治敏感、不当价值观",
    },
    "16-18": {
        "max_question_length": 200,
        "max_option_length": 50,
        "language_level": "接近成人表达，可包含抽象概念",
        "scenario_examples": "学术论文、实验报告、社会分析",
        "avoid": "暴力、恐怖、政治敏感、偏见歧视",
    },
}


def build_question_generation_prompt(
    age_group: str,
    subject: str,
    course_topic: str,
    difficulty: str,
    question_type: str,
    question_count: int,
    avoid_list: list[dict] = None,
    skill_hints: list[dict] = None,
    error_patterns: list[dict] = None,
    coverage_gaps: list[str] = None,
    control_signal: dict = None,
    revision_notes: str = "",
) -> list[dict[str, str]]:
    """
    构建出题 Prompt

    Args:
        age_group: 年龄分级
        subject: 学科
        course_topic: 课程主题
        difficulty: 难度
        question_type: 题型
        question_count: 本次生成数量
        avoid_list: 需要避免的题目列表
        skill_hints: Skill 策略提示
        error_patterns: 错误模式
        coverage_gaps: 知识覆盖缺口
        control_signal: 控制信号
        revision_notes: 上次审题未通过时的修订意见

    Returns:
        消息列表
    """
    req = AGE_REQUIREMENTS.get(age_group, AGE_REQUIREMENTS["10-12"])

    # 构建避免段落
    avoid_section = ""
    if avoid_list:
        previews = []
        for item in avoid_list[:10]:  # 最多展示10道避免题
            preview = item.get("question_body_preview", "")
            if preview:
                previews.append(f"- {preview}")
        if previews:
            avoid_section = f"""
## 避免重复
以下是已存在的相似题目，请避免生成相同或过于相似的题目：
{chr(10).join(previews)}
"""

    # Skill 提示段落
    skill_section = ""
    if skill_hints:
        hints = [f"- {h.get('hint', '')}" for h in skill_hints[:5]]
        if hints:
            skill_section = f"""
## Skill 策略提示
{chr(10).join(hints)}
"""

    # 错误模式段落
    error_section = ""
    if error_patterns:
        patterns = [f"- {p.get('pattern', '')}: {p.get('suggestion', '')}" for p in error_patterns[:5]]
        if patterns:
            error_section = f"""
## 已知错误模式（避免踩坑）
{chr(10).join(patterns)}
"""

    # 覆盖缺口段落
    gap_section = ""
    if coverage_gaps:
        gap_section = f"""
## 知识覆盖缺口（优先覆盖）
{', '.join(coverage_gaps[:10])}
"""

    # 控制信号段落
    control_section = ""
    if control_signal:
        adj = control_signal.get("adjustments", {})
        state = control_signal.get("state_estimate", {})
        control_section = f"""
## 当前控制信号
- 难度调整: delta={adj.get('difficulty_delta', 0)}
- 重复风险: {state.get('duplicate_risk', 0.0)}
- 用户能力估计: {state.get('ability', 0.5)}
"""

    system_prompt = f"""你是一位专业的教育出题专家。请根据以下要求生成高质量的题目。

## 版本: {PROMPT_VERSION}

## 基本要求
- 年龄分级: {age_group}
- 学科: {subject}
- 课程主题: {course_topic}
- 难度: {difficulty}
- 题型: {question_type}
- 生成数量: {question_count}

## 适龄性要求
- 题干最长 {req['max_question_length']} 字
- 选项最长 {req['max_option_length']} 字
- 语言水平: {req['language_level']}
- 推荐场景: {req['scenario_examples']}
- 禁止内容: {req['avoid']}
{avoid_section}{skill_section}{error_section}{gap_section}{control_section}

## 审题修订意见
{revision_notes or "无。请直接按基本要求生成题目。"}

## 输出格式
请以 JSON 数组格式输出题目：
[
  {{
    "question_type": "{question_type}",
    "question_body": "题干内容",
    "options": [{{"key": "A", "value": "选项内容"}}, ...],
    "correct_answer": "正确答案",
    "explanation": "详细解析",
    "tags": ["知识点标签"],
    "difficulty": "实际难度"
  }}
]

## 题目质量标准
1. 答案必须绝对正确，无歧义
2. 选项（除正确答案外）必须有合理的干扰性，不能明显错误
3. 解析要清晰、准确、有教育价值
4. 题干语言流畅、无歧义
5. 每道题的知识点标签要准确
"""

    messages = [{"role": "system", "content": system_prompt}]

    return messages
