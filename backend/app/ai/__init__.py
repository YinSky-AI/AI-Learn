"""
AI 出题 Harness 系统

实现 8 层闭环控制架构：
- 内环（出题级闭环）：L1-L7
- 外环（系统级监控）：ErrorLogger 中间件
- 学习环（进化级）：L8 SummaryAgent

v0.1 约束：
- 不实现联网搜索，不调用搜索 API
- 所有 Prompt 模板必须版本化管理
- AI 回复必须经过安全过滤
- 每个 Agent 必须声明偏差（deviation_declaration）
- FeedbackAggregator 是唯一的控制信号生产者
- ErrorLogger 不得自行修复错误，只分类和路由
- SummaryAgent 每次提炼记忆不超过 5 条
- Skill 文件大小不超过 15KB
- 记忆 TTL 默认 90 天
"""
