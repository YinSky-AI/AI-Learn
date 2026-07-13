"""
Agent 层 — 8 层闭环控制

Agent 排列顺序：
- L1 CourseIntentAgent: 理解课程选择，补齐结构化参数
- L2 QuestionPlannerAgent: 规划题型、数量、难度分布
- L3 QuestionMemoryAgent: 检索生成题目知识库、历史题、错题、用户偏好
- L4 QuestionGeneratorAgent: 生成题目、选项、答案、解析
- L5 QualityCheckAgent: 快速检查（答案正确性、适龄性、难度匹配、重复度）
- L6 SafetyAuditAgent: 四维安全审查（适龄性/准确性/公平性/隐私）
- L6 QualityReviewAgent: 抽样深度质量评估 + 趋势分析
- L8 SummaryAgent: Hermes五环（记忆策划/Skill创建/Skill自改进/跨会话召回/用户建模）
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
