"""
backend/app/ai/prompts/__init__.py

Prompt 模板层 —— 版本化管理的 Prompt 模板包

本包集中管理所有 Agent 使用的 Prompt 模板，确保 Prompt 工程的可维护性、
可追溯性和一致性。所有模板通过 PROMPT_VERSION 常量标识版本，
支持按版本灰度发布和回滚。

模板列表：
- course_intent: 课程意图理解 Prompt（L1 CourseIntentAgent）
- question_planning: 出题规划 Prompt（L2 QuestionPlannerAgent）
- question_generation: 出题 Prompt 模板（L4 QuestionGeneratorAgent，按年龄+学科+难度+题型）
- quality_check: 质量检查 Prompt 模板（L5 QualityCheckAgent）
- safety_audit: 安全审计 Prompt 模板（L6 SafetyAuditAgent）
- summary: 会话总结 Prompt（L8 SummaryAgent）

版本管理规范：
- 版本号格式：v{major}.{minor}.{patch}
- 每次 Prompt 变更必须升级版本号
- Agent 调用时必须传入 prompt_version 以便追溯
"""
