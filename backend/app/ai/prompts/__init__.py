"""
Prompt 模板层 — 版本化管理的 Prompt 模板

所有 Prompt 模板必须版本化管理，通过 PROMPT_VERSION 常量标识当前版本。

模板列表：
- course_intent: 课程意图理解 Prompt
- question_planning: 出题规划 Prompt
- question_generation: 出题 Prompt 模板（按年龄+学科+难度+题型）
- quality_check: 质量检查 Prompt 模板
- safety_audit: 安全审计 Prompt 模板
- summary: 会话总结 Prompt
"""
