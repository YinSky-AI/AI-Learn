"""
backend/app/ai/schemas.py

AI 出题 Harness 系统 —— 接口契约 Schema 定义模块

本模块定义了 8 层闭环控制架构中各 Agent 之间的数据接口契约，
基于 agents/06_sub_agent_tasks.md §2.11 规范实现。
所有 Schema 使用 Pydantic BaseModel，确保类型安全、运行时校验和序列化能力。

接口契约表：
- IntentParams: CourseIntentAgent(L1) -> QuestionPlannerAgent(L2)
- PlanResult: QuestionPlannerAgent(L2) -> QuestionGeneratorAgent(L4)
- MemoryContext: QuestionMemoryAgent(L3) -> QuestionGeneratorAgent(L4)
- GeneratedQuestions: QuestionGeneratorAgent(L4) -> QualityCheckAgent(L5)
- QuickCheckResult: QualityCheckAgent(L5) -> FeedbackAggregator
- SafetyAuditResult: SafetyAuditAgent(L6) -> FeedbackAggregator + ErrorLogger
- QualityTrendReport: QualityReviewAgent(L6) -> FeedbackAggregator
- ControlSignal: FeedbackAggregator(L7) -> L2/L3/L4
- MemoryItem: SummaryAgent(L8) -> SessionMemory表
- SkillFileData: SummaryAgent(L8) -> Skill存储
- UserProfileUpdate: SummaryAgent(L8) -> User表
- ErrorEvent: ErrorLogger -> ErrorLog表
- ToolCallRecord: 工具调用日志

设计原则：
- 每个 Schema 明确标注生产者和消费者
- 字段注释包含取值范围、默认值和业务含义
- 枚举类型约束取值空间，防止非法值流入下游
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# 枚举类型
# ============================================================================

class AgeGroup(str, Enum):
    """年龄分级"""
    AGE_06_09 = "6-9"
    AGE_10_12 = "10-12"
    AGE_13_15 = "13-15"
    AGE_16_18 = "16-18"


class Subject(str, Enum):
    """学科"""
    SUBJ_MATH = "数学"
    SUBJ_CHINESE = "语文"
    SUBJ_ENGLISH = "英语"
    SUBJ_SCIENCE = "科学"
    SUBJ_HISTORY = "历史"
    SUBJ_CODE = "编程"
    SUBJ_ART = "艺术"


class DifficultyLevel(str, Enum):
    """难度级别"""
    DIFF_EASY = "easy"
    DIFF_MEDIUM = "medium"
    DIFF_HARD = "hard"


class QuestionType(str, Enum):
    """题目类型"""
    CHOICE = "choice"                # 单选题
    MULTIPLE_CHOICE = "multiple_choice"  # 多选题
    FILL_BLANK = "fill_blank"        # 填空题
    SHORT_ANSWER = "short_answer"    # 简答题
    TRUE_FALSE = "true_false"        # 判断题


class ErrorType(str, Enum):
    """错误类型"""
    SAFE_AUDIT = "SAFE_AUDIT"        # E001-E099 内容安全违规
    QUALITY_FAIL = "QUALITY_FAIL"    # E100-E199 质量检查失败
    PERF_DEGRADE = "PERF_DEGRADE"    # E200-E299 性能退化
    LOGIC_ERROR = "LOGIC_ERROR"      # E300-E399 逻辑错误


class ErrorSeverity(str, Enum):
    """错误严重度"""
    P0 = "P0"  # 立即阻断
    P1 = "P1"  # 本轮内处理
    P2 = "P2"  # 记录并监控


class HarnessRunStatus(str, Enum):
    """Harness 执行状态"""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SafetyVerdict(str, Enum):
    """安全审查结果"""
    PASS = "PASS"
    REJECT = "REJECT"


class MemoryType(str, Enum):
    """记忆类型"""
    ERROR_PATTERN = "error_pattern"          # 错误模式
    PREFERENCE = "preference"                # 用户偏好
    QUALITY_INSIGHT = "quality_insight"      # 质量洞察
    BEHAVIOR_PATTERN = "behavior_pattern"    # 行为模式


class EvolutionType(str, Enum):
    """进化类型"""
    SKILL_CREATED = "skill_created"
    SKILL_UPDATED = "skill_updated"
    MEMORY_CLEANED = "memory_cleaned"
    STRATEGY_CHANGED = "strategy_changed"


class QualityTrend(str, Enum):
    """质量趋势"""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


# ============================================================================
# L1 -> L2: IntentParams
# ============================================================================

class IntentParams(BaseModel):
    """
    课程意图参数
    生产者: CourseIntentAgent (L1)
    消费者: QuestionPlannerAgent (L2)
    """
    age_group: str = Field(..., description="年龄分级，如 '6-9', '10-12'")
    subject: str = Field(..., description="学科，如 '数学', '语文'")
    course_topic: str = Field(..., description="课程主题，如 '分数加法', '古诗词鉴赏'")
    difficulty: str = Field(..., description="难度级别: easy/medium/hard")
    question_types: list[str] = Field(
        default_factory=lambda: ["choice", "fill_blank"],
        description="题型列表"
    )
    question_count: int = Field(default=10, ge=1, le=50, description="题目数量")
    learning_goal: Optional[str] = Field(None, description="学习目标描述")
    raw_input: Optional[str] = Field(None, description="用户原始输入")
    clarification_required: bool = Field(False, description="是否需要用户澄清")


# ============================================================================
# L2 -> L4: PlanResult
# ============================================================================

class QuestionPlanItem(BaseModel):
    """单条题目规划"""
    type: str = Field(..., description="题型")
    count: int = Field(..., ge=1, description="数量")
    difficulty: str = Field(..., description="难度级别")
    weight: float = Field(default=1.0, description="权重，用于分配生成资源")


class DeviationDeclaration(BaseModel):
    """偏差声明 — Agent 必须在输出偏离设定值时声明"""
    type: str = Field(..., description="偏差类型，如 difficulty_mismatch, count_adjusted")
    expected: str = Field(..., description="期望值")
    actual: str = Field(..., description="实际值")
    reason: str = Field(..., description="偏差原因")


class PlanResult(BaseModel):
    """
    出题规划结果
    生产者: QuestionPlannerAgent (L2)
    消费者: QuestionGeneratorAgent (L4)
    """
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_plan: list[QuestionPlanItem] = Field(..., description="题目规划列表")
    adjusted_params: dict[str, Any] = Field(
        default_factory=dict,
        description="经过 ControlSignal 调整后的参数"
    )
    deviation_declaration: Optional[DeviationDeclaration] = Field(
        None, description="偏差声明，如有偏离必须填写"
    )


# ============================================================================
# L3 -> L4: MemoryContext
# ============================================================================

class SimilarQuestion(BaseModel):
    """相似题目（去重用）"""
    id: str = Field(..., description="题目 ID")
    similarity_hash: str = Field(..., description="去重指纹")
    question_body_preview: str = Field("", description="题干预览（前50字）")
    similarity_score: float = Field(0.0, description="相似度分数")


class MemoryContext(BaseModel):
    """
    记忆上下文
    生产者: QuestionMemoryAgent (L3)
    消费者: QuestionGeneratorAgent (L4)
    """
    avoid_list: list[SimilarQuestion] = Field(
        default_factory=list,
        description="需要避免的重复/相似题目"
    )
    recent_feedback: list[dict[str, Any]] = Field(
        default_factory=list,
        description="最近的答题反馈"
    )
    user_preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="用户偏好（题型、场景、难度倾向等）"
    )
    skill_hints: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Skill 文件中的策略提示"
    )
    error_patterns: list[dict[str, Any]] = Field(
        default_factory=list,
        description="用户历史错题模式"
    )
    coverage_gaps: list[str] = Field(
        default_factory=list,
        description="知识点覆盖缺口"
    )


# ============================================================================
# L4 -> L5: GeneratedQuestions
# ============================================================================

class GeneratedQuestion(BaseModel):
    """单道生成题目"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_type: str = Field(..., description="题型")
    question_body: str = Field(..., description="题干")
    options: Optional[list[dict[str, str]]] = Field(
        None, description="选项列表，选择题专用 [{key: 'A', value: '...'}]"
    )
    correct_answer: str = Field(..., description="正确答案")
    explanation: str = Field(..., description="解析")
    tags: list[str] = Field(default_factory=list, description="知识点标签")
    difficulty: str = Field(..., description="实际难度")
    similarity_hash: str = Field("", description="去重指纹")


class GenerationMeta(BaseModel):
    """生成元信息"""
    model_name: str = Field("", description="使用的模型名称")
    prompt_version: str = Field("", description="Prompt 模板版本")
    total_tokens: int = Field(0, description="Token 消耗")
    latency_ms: int = Field(0, description="生成耗时（毫秒）")


class GeneratedQuestions(BaseModel):
    """
    生成题目批次
    生产者: QuestionGeneratorAgent (L4)
    消费者: QualityCheckAgent (L5)
    """
    questions: list[GeneratedQuestion] = Field(..., description="生成题目列表")
    generation_meta: GenerationMeta = Field(
        default_factory=GenerationMeta, description="生成元信息"
    )
    deviation_declaration: Optional[DeviationDeclaration] = Field(
        None, description="偏差声明"
    )


# ============================================================================
# L5 -> L7: QuickCheckResult
# ============================================================================

class QualityIssue(BaseModel):
    """质量问题"""
    dimension: str = Field(..., description="检查维度: answer/age/difficulty/duplicate")
    detail: str = Field(..., description="问题描述")
    severity: str = Field("warning", description="严重度: warning/blocking")


class QualityDeviation(BaseModel):
    """质量偏差信号"""
    type: str = Field(..., description="偏差类型")
    value: float = Field(..., description="偏差值")


class QuickCheckResult(BaseModel):
    """
    快速检查结果
    生产者: QualityCheckAgent (L5)
    消费者: FeedbackAggregator (L7)
    """
    question_id: str = Field(..., description="被检查题目 ID")
    passed: bool = Field(..., description="是否通过")
    score: float = Field(..., ge=0, le=100, description="质量分数 (0-100)")
    issues: list[QualityIssue] = Field(
        default_factory=list, description="质量问题列表"
    )
    deviation: QualityDeviation = Field(
        default_factory=lambda: QualityDeviation(type="quality", value=0.0),
        description="偏差信号"
    )


# ============================================================================
# L6 -> L7: SafetyAuditResult
# ============================================================================

class SafetyScore(BaseModel):
    """安全审查四维评分"""
    age_appropriate: float = Field(..., ge=0, le=10, description="适龄性评分")
    accuracy: float = Field(..., ge=0, le=10, description="准确性评分")
    fairness: float = Field(..., ge=0, le=10, description="公平性评分")
    privacy: float = Field(..., ge=0, le=10, description="隐私安全评分")


class SafetyIssue(BaseModel):
    """安全问题"""
    dimension: str = Field(..., description="问题维度")
    detail: str = Field(..., description="问题描述")
    severity: str = Field(..., description="严重度: blocking/warning")


class SafetyAuditResult(BaseModel):
    """
    安全审查结果
    生产者: SafetyAuditAgent (L6)
    消费者: FeedbackAggregator (L7) + ErrorLogger
    """
    question_id: str = Field(..., description="被审查题目 ID")
    verdict: SafetyVerdict = Field(..., description="审查结论: PASS/REJECT")
    scores: SafetyScore = Field(..., description="四维评分")
    issues: list[SafetyIssue] = Field(
        default_factory=list, description="问题列表"
    )
    blocking_issue: Optional[str] = Field(None, description="否决原因")


# ============================================================================
# L6 -> L7: QualityTrendReport
# ============================================================================

class AgentFeedback(BaseModel):
    """Agent 级别反馈"""
    strength: str = Field("", description="优势")
    weakness: str = Field("", description="不足")
    missed_issues: Optional[str] = Field(None, description="遗漏问题")


class TopIssue(BaseModel):
    """Top 质量问题"""
    type: str = Field(..., description="问题类型")
    frequency: str = Field("", description="频率")
    suggestion: str = Field("", description="改进建议")


class QualityTrendReport(BaseModel):
    """
    质量趋势报告
    生产者: QualityReviewAgent (L6)
    消费者: FeedbackAggregator (L7)
    """
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trend: QualityTrend = Field(QualityTrend.STABLE, description="质量趋势")
    system_quality_score: float = Field(0.0, ge=0, le=100, description="系统质量分")
    top_issues: list[TopIssue] = Field(
        default_factory=list, description="Top 问题列表"
    )
    agent_feedback: dict[str, AgentFeedback] = Field(
        default_factory=dict, description="Agent 级别反馈"
    )
    recommended_adjustments: dict[str, float] = Field(
        default_factory=dict, description="推荐调整参数"
    )


# ============================================================================
# L7 -> L2/L3/L4: ControlSignal
# ============================================================================

class PIDValues(BaseModel):
    """PID 三分量"""
    p_error: float = Field(0.0, description="比例分量：当前批次通过率偏差值")
    i_drift: str = Field("stable", description="积分分量：累计偏差方向 (improving/stable/declining)")
    d_slope: str = Field("zero", description="微分分量：质量变化斜率 (positive/negative/zero)")


class Adjustments(BaseModel):
    """控制信号调整建议"""
    difficulty_delta: float = Field(0.0, description="难度调整建议 (-1/0/+1)")
    count_delta: int = Field(0, description="题目数量调整建议")
    topic_scope: str = Field("", description="知识点覆盖范围建议")


class StateEstimate(BaseModel):
    """系统状态观测器"""
    quality_baseline: float = Field(0.0, description="最近50题平均质量分")
    ability: float = Field(0.5, description="用户能力估计 (0-1)")
    coverage: float = Field(0.0, description="知识点覆盖度 (0-1)")
    duplicate_risk: float = Field(0.0, description="题目重复风险 (0-1)")


class ControlSignal(BaseModel):
    """
    控制信号
    生产者: FeedbackAggregator (L7)（唯一控制信号生产者）
    消费者: QuestionPlannerAgent(L2) + QuestionMemoryAgent(L3) + QuestionGeneratorAgent(L4)
    """
    pid: PIDValues = Field(default_factory=PIDValues)
    adjustments: Adjustments = Field(default_factory=Adjustments)
    state_estimate: StateEstimate = Field(default_factory=StateEstimate)
    iteration: int = Field(0, description="当前循环编号")


# ============================================================================
# L8 -> DB: MemoryItem / SkillFile / UserProfileUpdate
# ============================================================================

class MemoryItem(BaseModel):
    """
    会话记忆项
    生产者: SummaryAgent (L8)
    消费者: SessionMemory 表
    """
    type: MemoryType = Field(..., description="记忆类型")
    content: str = Field(..., description="结构化记忆内容")
    confidence: float = Field(0.5, ge=0, le=1, description="置信度")
    ttl_days: int = Field(90, description="生存天数，默认90天")
    related_topic: str = Field("", description="关联主题")


class SkillFileData(BaseModel):
    """
    Skill 文件数据
    生产者: SummaryAgent (L8)
    消费者: Skill 存储
    """
    name: str = Field(..., description="Skill 名称")
    trigger: dict[str, Any] = Field(..., description="触发条件")
    version: int = Field(1, description="版本号")
    steps: list[str] = Field(default_factory=list, description="执行步骤")
    preferences: list[str] = Field(default_factory=list, description="用户偏好记录")
    pitfalls: list[str] = Field(default_factory=list, description="常见陷阱")
    success_count: int = Field(0, description="使用成功次数")


class AbilityUpdate(BaseModel):
    """能力更新"""
    level: str = Field("", description="能力等级")
    accuracy: float = Field(0.0, ge=0, le=1, description="准确率")
    trend: str = Field("stable", description="趋势: improving/stable/declining")


class UserProfileUpdate(BaseModel):
    """
    用户画像更新
    生产者: SummaryAgent (L8)
    消费者: User 表
    """
    ability_updates: dict[str, AbilityUpdate] = Field(
        default_factory=dict, description="能力估计更新"
    )
    behavior_patterns: dict[str, Any] = Field(
        default_factory=dict, description="行为模式更新"
    )
    preference_conflicts: list[dict[str, str]] = Field(
        default_factory=list, description="偏好冲突"
    )
    confidence_updates: dict[str, float] = Field(
        default_factory=dict, description="置信度更新"
    )


# ============================================================================
# ErrorLogger -> DB: ErrorEvent
# ============================================================================

class ErrorEvent(BaseModel):
    """
    错误事件
    生产者: ErrorLogger (中间件)
    消费者: ErrorLog 表 + 路由 Agent
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_name: str = Field(..., description="出错 Agent 名称")
    step_name: str = Field(..., description="步骤名称")
    error_type: ErrorType = Field(..., description="错误类型")
    error_code: str = Field(..., description="错误编码 (E001-E399)")
    severity: ErrorSeverity = Field(..., description="严重度")
    raw_error: str = Field(..., description="原始错误信息")
    context: Optional[dict[str, Any]] = Field(None, description="错误上下文")
    affected_output: Optional[dict[str, Any]] = Field(None, description="受影响的输出")
    routing_target: Optional[str] = Field(None, description="路由目标 Agent")
    auto_fix_attempted: bool = Field(False, description="是否尝试自动修复（恒为 False）")


# ============================================================================
# 工具调用日志: ToolCallRecord
# ============================================================================

class ToolCallRecord(BaseModel):
    """
    工具调用日志记录
    所有工具调用必须记录以下字段
    """
    step_name: str = Field(..., description="步骤名称")
    tool_name: str = Field(..., description="工具名")
    input_summary: dict[str, Any] = Field(..., description="输入摘要")
    output_summary: Optional[dict[str, Any]] = Field(None, description="输出摘要")
    latency_ms: int = Field(0, description="耗时（毫秒）")
    status: str = Field("succeeded", description="状态: succeeded/failed")
    error_message: Optional[str] = Field(None, description="错误信息")
    error_type: Optional[str] = Field(None, description="错误类型")


# ============================================================================
# Harness 执行上下文
# ============================================================================

class HarnessRunContext(BaseModel):
    """Harness 执行上下文 — 贯穿整个生成流程"""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="用户 ID")
    run_type: str = Field("question_generation", description="运行类型")
    status: HarnessRunStatus = Field(HarnessRunStatus.RUNNING)
    input_payload: dict[str, Any] = Field(default_factory=dict, description="输入参数")
    output_summary: Optional[dict[str, Any]] = Field(None, description="输出摘要")
    model_usage: dict[str, Any] = Field(
        default_factory=dict, description="模型用量统计"
    )
    error_message: Optional[str] = Field(None, description="错误信息")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None, description="结束时间")
    tool_call_logs: list[ToolCallRecord] = Field(
        default_factory=list, description="工具调用日志"
    )
    error_events: list[ErrorEvent] = Field(
        default_factory=list, description="错误事件列表"
    )
    control_signal: Optional[ControlSignal] = Field(
        None, description="当前控制信号"
    )
    iteration: int = Field(0, description="当前循环编号")
    prompt_version: str = Field("v0.1.0", description="Prompt 模板版本")
