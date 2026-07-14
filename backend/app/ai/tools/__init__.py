"""
backend/app/ai/tools/__init__.py

工具层 —— Agent 可调用的副作用工具包

本包提供 AI 出题系统中所有与外部存储交互的副作用工具。
所有工具遵循统一的调用日志规范，确保操作可追溯、可审计。

工具列表：
- QuestionMemoryTool: 生成题目知识库检索（PostgreSQL tsvector + pg_trgm）
- QuestionSaveTool: 题目保存工具（持久化通过的题目到数据库）
- AuditLogTool: 审计日志工具（记录安全审查、质量检查、控制信号）
- SkillRetrievalTool: Skill 检索工具（从 Skill 目录检索匹配策略）

调用日志规范：
所有工具调用必须记录以下字段：
- tool_name: 工具名称
- input: 输入参数摘要
- output_summary: 输出结果摘要
- latency_ms: 执行耗时（毫秒）
- status: 执行状态（succeeded / failed）
- error: 错误信息（如有）

设计原则：
- 工具与 Agent 解耦，支持独立测试
- 数据库会话由 Harness 注入，支持无数据库降级运行
- 所有异常内部捕获并记录，不向上传播阻断主流程
"""
