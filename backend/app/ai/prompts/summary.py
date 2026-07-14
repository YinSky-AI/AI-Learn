"""
backend/app/ai/prompts/summary.py

会话总结 Prompt 模板

本模板集合用于 L8 SummaryAgent 的 Hermes 五环机制，
支持从会话数据中提炼记忆、创建 Skill 和更新用户画像。

版本: v0.1.0
Agent: SummaryAgent (L8)
用途: Hermes五环 — 记忆策划、Skill创建、Skill自改进、跨会话召回、用户建模

包含模板：
- build_memory_distill_prompt: 环1 记忆策划，提炼 ≤5 条高价值记忆
- build_skill_creation_prompt: 环2 Skill创建，将成功模式蒸馏为可复用 Skill
- build_user_profile_update_prompt: 环5 用户建模，更新能力估计和行为模式

记忆类型：
- error_pattern: 用户反复犯的错误模式
- preference: 用户偏好（题型、场景等）
- quality_insight: 质量洞察
- behavior_pattern: 行为模式（答题时长、连胜后放松等）
"""

PROMPT_VERSION = "v0.1.0"


def build_memory_distill_prompt(
    session_data: dict,
    user_id: str,
    existing_memories: list[dict] = None,
) -> list[dict[str, str]]:
    """
    构建记忆提炼 Prompt（Hermes 环1: 记忆策划）

    Args:
        session_data: 会话数据（答题记录、生成记录、质量检查数据等）
        user_id: 用户 ID
        existing_memories: 已有记忆（避免重复）

    Returns:
        消息列表
    """
    existing_section = ""
    if existing_memories:
        mem_list = [f"- [{m.get('type', '')}] {m.get('content', '')[:80]}" for m in existing_memories[:5]]
        existing_section = f"""
## 已有记忆（避免重复）
{chr(10).join(mem_list)}
"""

    system_prompt = f"""你是一位学习数据分析专家。请从本次学习会话中提炼不超过 5 条高价值记忆。

## 版本: {PROMPT_VERSION}

## 记忆类型
1. **error_pattern**: 用户反复犯的错误模式（如"分数加法时忘记通分"）
2. **preference**: 用户偏好（如"喜欢场景化题目"、"偏好选择题"）
3. **quality_insight**: 质量洞察（如"该主题生成题的正确率偏高"）
4. **behavior_pattern**: 行为模式（如"平均每题答题时间30秒"、"连续答对后易放松"）

## 筛选标准
- 优先存储高置信度（>0.7）的信息
- 优先存储可复用的模式（非一次性行为）
- 优先存储对后续出题有指导意义的信息
- 总数不超过 5 条，只保留最有价值的

## 会话数据
用户: {user_id}
{existing_section}
``json
{session_data}
```

## 输出格式
请以 JSON 数组输出记忆项（不超过5条）：
[
  {{
    "type": "error_pattern/preference/quality_insight/behavior_pattern",
    "content": "结构化记忆内容",
    "confidence": 0.0-1.0,
    "ttl_days": 90,
    "related_topic": "关联主题"
  }}
]
"""

    messages = [{"role": "system", "content": system_prompt}]

    return messages


def build_skill_creation_prompt(
    success_pattern: dict,
    topic: str,
) -> list[dict[str, str]]:
    """
    构建 Skill 创建 Prompt（Hermes 环2: Skill创建）

    Args:
        success_pattern: 成功模式数据
        topic: 关联主题

    Returns:
        消息列表
    """
    system_prompt = f"""你是一位教育策略专家。请将以下成功出题模式蒸馏为可复用的 Skill 文件。

## 版本: {PROMPT_VERSION}

## 成功模式数据
```json
{success_pattern}
```

## Skill 文件格式要求
```yaml
---
name: "Skill名称"
trigger: "触发条件（学科+主题+年龄+难度）"
created: "创建日期"
version: 1
success_count: 0
---

## 执行步骤
（具体、可操作的出题步骤）

## 用户偏好记录
（该场景下用户的偏好）

## 常见陷阱
（需要避免的错误模式）
```

## 约束
- Skill 文件大小不超过 15KB
- 触发条件必须明确可匹配
- 执行步骤必须足够具体
- 必须包含用户偏好和已知陷阱

请生成 Skill 文件内容。
"""

    messages = [{"role": "system", "content": system_prompt}]

    return messages


def build_user_profile_update_prompt(
    session_data: dict,
    current_profile: dict,
) -> list[dict[str, str]]:
    """
    构建用户画像更新 Prompt（Hermes 环5: 用户建模）

    Args:
        session_data: 会话数据
        current_profile: 当前用户画像

    Returns:
        消息列表
    """
    system_prompt = f"""你是一位用户行为分析专家。请根据本次学习会话更新用户画像。

## 版本: {PROMPT_VERSION}

## 当前用户画像
```json
{current_profile}
```

## 本次会话数据
```json
{session_data}
```

## 输出格式
请以 JSON 格式输出更新内容：
{{
    "ability_updates": {{
        "学科/知识点": {{
            "level": "等级",
            "accuracy": 0.0-1.0,
            "trend": "improving/stable/declining"
        }}
    }},
    "behavior_patterns": {{
        "avg_session_minutes": 平均会话时长,
        "preferred_types": ["偏好题型"],
        "active_hours": [活跃时段]
    }},
    "preference_conflicts": [
        {{
            "claimed": "用户声称的偏好",
            "actual": "实际行为",
            "resolution": "以实际行为为准"
        }}
    ],
    "confidence_updates": {{
        "学科/知识点": 置信度
    }}
}}

## 更新原则
- 反馈一致性 < 70% 时不更新策略（防止噪声污染）
- 以实际行为数据为准，而非用户声称的偏好
- 置信度更新需渐进，单次更新幅度不超过 ±0.15
"""

    messages = [{"role": "system", "content": system_prompt}]

    return messages
