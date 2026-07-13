"""
出题规划 Prompt 模板

版本: v0.1.0
Agent: QuestionPlannerAgent (L2)
用途: 规划题型、数量、难度分布
"""

PROMPT_VERSION = "v0.1.0"


def build_question_planning_prompt(
    age_group: str,
    subject: str,
    course_topic: str,
    difficulty: str,
    question_types: list[str],
    question_count: int,
    learning_goal: str = "",
    control_signal: dict = None,
) -> list[dict[str, str]]:
    """
    构建出题规划 Prompt

    Args:
        age_group: 年龄分级
        subject: 学科
        course_topic: 课程主题
        difficulty: 难度
        question_types: 题型列表
        question_count: 题目数量
        learning_goal: 学习目标
        control_signal: 控制信号（来自 FeedbackAggregator）

    Returns:
        消息列表
    """
    # 控制信号段落
    control_section = ""
    if control_signal:
        pid = control_signal.get("pid", {})
        adj = control_signal.get("adjustments", {})
        state = control_signal.get("state_estimate", {})
        control_section = f"""
## 当前控制信号（来自 FeedbackAggregator，你必须据此调整规划）
- PID 比例分量 (p_error): {pid.get('p_error', 0)}
- PID 积分分量 (i_drift): {pid.get('i_drift', 'stable')}
- PID 微分分量 (d_slope): {pid.get('d_slope', 'zero')}
- 难度调整建议 (difficulty_delta): {adj.get('difficulty_delta', 0)}
- 数量调整建议 (count_delta): {adj.get('count_delta', 0)}
- 知识覆盖范围建议 (topic_scope): {adj.get('topic_scope', '无')}
- 用户能力估计 (ability): {state.get('ability', 0.5)}
- 知识覆盖度 (coverage): {state.get('coverage', 0.0)}
- 重复风险 (duplicate_risk): {state.get('duplicate_risk', 0.0)}
"""

    system_prompt = f"""你是一位教育出题规划专家。你的任务是根据课程参数，规划具体的出题方案。

## 版本: {PROMPT_VERSION}

## 规划要求
请输出 JSON 格式的出题规划：
{{
    "question_plan": [
        {{
            "type": "题型",
            "count": 数量,
            "difficulty": "easy/medium/hard",
            "weight": 权重(0.5-2.0)
        }}
    ],
    "adjusted_params": {{
        "total_count": 实际总题数,
        "difficulty_distribution": {{
            "easy": 基础题占比,
            "medium": 中等题占比,
            "hard": 挑战题占比
        }},
        "reasoning": "规划理由"
    }},
    "deviation_declaration": null 或 {{
        "type": "偏差类型",
        "expected": "期望值",
        "actual": "实际值",
        "reason": "偏差原因"
    }}
}}

## 规划规则
1. 题目总数应接近请求数量，可适当调整（±20%）
2. 难度分布应遵循"金字塔原则"：基础题40%，中等题40%，挑战题20%
3. 如果 difficulty_delta > 0，增加挑战题比例；如果 < 0，增加基础题比例
4. 如果 duplicate_risk > 0.5，适当增加 variety（题型多样性）
5. 如果 coverage < 0.5，优先覆盖缺口知识点
6. 题型权重影响生成资源的分配

## 课程参数
- 年龄分级: {age_group}
- 学科: {subject}
- 课程主题: {course_topic}
- 目标难度: {difficulty}
- 可选题型: {', '.join(question_types)}
- 请求题数: {question_count}
- 学习目标: {learning_goal or '无特定目标'}
{control_section}
"""

    messages = [{"role": "system", "content": system_prompt}]

    return messages
