"""
backend/app/ai/agents/__init__.py

Agent 层 —— 8 层闭环控制模块包

本包聚合了 AI 出题系统中全部 8 层 Agent，实现从意图理解到质量审查、
从安全审计到进化学习的完整闭环。各 Agent 通过统一的 BaseAgent 基类
实现标准化接口，确保可替换、可观测、可测试。

Agent 排列顺序（数据流方向）：
- L1 CourseIntentAgent: 理解课程选择，补齐结构化参数
- L2 QuestionPlannerAgent: 规划题型、数量、难度分布
- L3 QuestionMemoryAgent: 检索生成题目知识库、历史题、错题、用户偏好
- L4 QuestionGeneratorAgent: 生成题目、选项、答案、解析
- L5 QualityCheckAgent: 快速检查（答案正确性、适龄性、难度匹配、重复度）
- L6 SafetyAuditAgent: 四维安全审查（适龄性/准确性/公平性/隐私）
- L6 QualityReviewAgent: 抽样深度质量评估 + 趋势分析
- L8 SummaryAgent: Hermes五环（记忆策划/Skill创建/Skill自改进/跨会话召回/用户建模）

使用方式：
    from backend.app.ai.agents import AIHarness
    harness = AIHarness()
    result = await harness.generate(...)
"""

from backend.app.ai.agents.base import BaseAgent
from backend.app.ai.agents.course_intent import CourseIntentAgent
from backend.app.ai.agents.question_planner import QuestionPlannerAgent
from backend.app.ai.agents.question_memory import QuestionMemoryAgent
from backend.app.ai.agents.question_generator import QuestionGeneratorAgent
from backend.app.ai.agents.quality_checker import QualityCheckAgent
from backend.app.ai.agents.safety_auditor import SafetyAuditAgent
from backend.app.ai.agents.quality_reviewer import QualityReviewAgent
from backend.app.ai.agents.summary_agent import SummaryAgent

__all__ = [
    "BaseAgent",
    "CourseIntentAgent",
    "QuestionPlannerAgent",
    "QuestionMemoryAgent",
    "QuestionGeneratorAgent",
    "QualityCheckAgent",
    "SafetyAuditAgent",
    "QualityReviewAgent",
    "SummaryAgent",
]
