"""
backend/app/ai/skills/__init__.py

Skill 存储和进化目录 —— 可复用策略知识库模块

本模块作为 AI 出题系统的 Skill 文件存储目录，用于 SummaryAgent（L8）
创建、更新和检索可复用的出题策略知识。Skill 是对成功出题模式的蒸馏，
包含执行步骤、用户偏好和常见陷阱，可被后续同场景出题复用。

Skill 文件规范：
- 格式：Markdown（.md）
- 大小：不超过 15KB
- 结构：YAML frontmatter + Markdown body
- 元数据：name, trigger, version, success_count, created

内容结构：
- 执行步骤：具体可操作的出题流程
- 用户偏好记录：该场景下用户的特定偏好
- 常见陷阱：需要避免的错误模式

使用方式：
- 创建：SummaryAgent 环2 在成功率 ≥80% 时自动创建
- 检索：QuestionMemoryAgent 通过 SkillRetrievalTool 按 trigger 匹配
- 更新：SummaryAgent 环3 根据新数据自改进 Skill 内容
"""
