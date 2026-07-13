"""
工具层 — Agent 可调用的副作用工具

工具列表：
- QuestionMemoryTool: 生成题目知识库检索（PostgreSQL tsvector + pg_trgm）
- QuestionSaveTool: 题目保存工具
- AuditLogTool: 审计日志工具
- SkillRetrievalTool: Skill 检索工具

所有工具调用必须记录 tool_name、input、output_summary、latency_ms、status、error
"""
