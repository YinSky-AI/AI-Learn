# -*- coding: utf-8 -*-
"""
AI 生成相关模型
包含 GeneratedQuestionBatch, GeneratedQuestion, QuestionQualityCheck,
HarnessRun, ToolCallLog, Skill, SessionMemory, ErrorLog, EvolutionRecord
"""

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, Index, ForeignKey, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import BaseModel
from app.models import Base


class GeneratedQuestionBatch(BaseModel, Base):
    """
    AI 生成题目批次
    记录每次 AI 出题请求的上下文和结果状态
    """

    __tablename__ = "generated_question_batches"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="发起生成的用户",
    )
    age_group_code = Column(String(10), nullable=False, comment="生成时使用的年龄分级")
    subject_code = Column(String(20), nullable=False, comment="学科")
    course_topic = Column(String(200), nullable=False, comment="课程主题")
    difficulty_level = Column(String(10), nullable=False, comment="难度")
    question_types = Column(JSONB, nullable=False, comment="题型列表")
    question_count = Column(Integer, nullable=False, comment="请求生成数量")
    learning_goal = Column(String(200), nullable=True, comment="学习目标")
    status = Column(
        String(20),
        default="pending",
        server_default="pending",
        comment="状态: pending / passed / failed / partial",
    )
    prompt_version = Column(String(50), nullable=False, comment="Prompt 模板版本")
    harness_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("harness_runs.id", ondelete="SET NULL"),
        nullable=True,
        comment="对应 Harness 执行记录",
    )

    # 关联
    generated_questions = relationship(
        "GeneratedQuestion",
        back_populates="batch_rel",
        cascade="all, delete-orphan",
    )

    # 索引
    __table_args__ = (
        Index("idx_gqb_user", "user_id"),
        Index("idx_gqb_topic", "subject_code", "course_topic"),
        Index("idx_gqb_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<GeneratedQuestionBatch(id={self.id}, status={self.status})>"


class GeneratedQuestion(BaseModel, Base):
    """
    AI 生成题目知识库
    沉淀历史生成题，用于去重、复习和错题变式
    """

    __tablename__ = "generated_questions"

    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generated_question_batches.id", ondelete="CASCADE"),
        nullable=False,
        comment="生成批次 ID",
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户 ID",
    )
    knowledge_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_nodes.id", ondelete="SET NULL"),
        nullable=True,
        comment="可选关联知识点",
    )
    subject_code = Column(String(20), nullable=False, comment="学科")
    course_topic = Column(String(200), nullable=False, comment="课程主题")
    difficulty_level = Column(String(10), nullable=False, comment="难度")
    question_type = Column(String(20), nullable=False, comment="题型")
    question_body = Column(Text, nullable=False, comment="题干")
    options = Column(JSONB, nullable=True, comment="选项")
    correct_answer = Column(Text, nullable=False, comment="正确答案")
    explanation = Column(Text, nullable=False, comment="解析")
    knowledge_tags = Column(JSONB, nullable=False, comment="知识点标签")
    source_prompt = Column(Text, nullable=False, comment="生成 Prompt 或 Prompt 摘要")
    similarity_hash = Column(String(128), nullable=True, comment="去重用指纹")
    quality_status = Column(
        String(20),
        default="unchecked",
        server_default="unchecked",
        comment="质量状态: unchecked / passed / failed",
    )
    parent_question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generated_questions.id", ondelete="SET NULL"),
        nullable=True,
        comment="变式题来源",
    )
    language = Column(
        String(10),
        default="zh-CN",
        server_default="zh-CN",
        comment="题目语言",
    )

    # 关联
    batch_rel = relationship("GeneratedQuestionBatch", back_populates="generated_questions")
    quality_checks = relationship(
        "QuestionQualityCheck",
        back_populates="question_rel",
        cascade="all, delete-orphan",
    )

    # 索引
    __table_args__ = (
        Index("idx_gq_user_topic", "user_id", "subject_code", "course_topic"),
        Index("idx_gq_diff", "difficulty_level"),
        Index("idx_gq_type", "question_type"),
        Index("idx_gq_language", "language"),
        Index("idx_gq_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<GeneratedQuestion(id={self.id}, type={self.question_type})>"


class QuestionQualityCheck(BaseModel, Base):
    """
    题目质量检查记录
    记录对 AI 生成题目的各项质量检查结果
    """

    __tablename__ = "question_quality_checks"

    generated_question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generated_questions.id", ondelete="CASCADE"),
        nullable=False,
        comment="被检查题目",
    )
    check_type = Column(
        String(50),
        nullable=False,
        comment="检查类型: answer / age / difficulty / duplicate / safety",
    )
    status = Column(
        String(20),
        nullable=False,
        comment="状态: passed / failed / warning",
    )
    score = Column(Float, nullable=True, comment="检查得分")
    message = Column(Text, nullable=True, comment="检查说明")
    checker_version = Column(String(50), nullable=False, comment="检查器版本")

    # 关联
    question_rel = relationship("GeneratedQuestion", back_populates="quality_checks")

    # 索引
    __table_args__ = (
        Index("idx_quality_question", "generated_question_id"),
        Index("idx_quality_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<QuestionQualityCheck(id={self.id}, type={self.check_type}, status={self.status})>"


class HarnessRun(BaseModel, Base):
    """
    AI Harness 执行记录
    记录一次 AI 调用链的完整执行情况
    """

    __tablename__ = "harness_runs"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户 ID",
    )
    run_type = Column(
        String(50),
        nullable=False,
        comment="执行类型: question_generation / variant_generation / ai_explain",
    )
    status = Column(
        String(20),
        nullable=False,
        comment="状态: running / succeeded / failed",
    )
    input_payload = Column(JSONB, nullable=False, comment="输入参数")
    output_summary = Column(JSONB, nullable=True, comment="输出摘要")
    model_usage = Column(JSONB, nullable=True, comment="Token、模型、耗时等使用信息")
    error_message = Column(Text, nullable=True, comment="错误信息")
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        comment="开始时间",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="结束时间",
    )

    # 关联
    tool_calls = relationship(
        "ToolCallLog",
        back_populates="harness_run_rel",
        cascade="all, delete-orphan",
    )

    # 索引
    __table_args__ = (
        Index("idx_harness_user", "user_id"),
        Index("idx_harness_type", "run_type"),
        Index("idx_harness_started", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<HarnessRun(id={self.id}, type={self.run_type}, status={self.status})>"


class ToolCallLog(BaseModel, Base):
    """
    工具调用日志
    记录 AI Harness 中每个工具步骤的调用情况
    """

    __tablename__ = "tool_call_logs"

    harness_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("harness_runs.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属 Harness Run",
    )
    step_name = Column(
        String(50),
        nullable=False,
        comment="步骤名称: intent / plan / memory / generate / quality / save",
    )
    tool_name = Column(String(100), nullable=False, comment="工具名称")
    input_summary = Column(JSONB, nullable=False, comment="输入摘要")
    output_summary = Column(JSONB, nullable=True, comment="输出摘要")
    latency_ms = Column(Integer, nullable=True, comment="耗时（毫秒）")
    status = Column(
        String(20),
        nullable=False,
        comment="状态: succeeded / failed",
    )
    error_message = Column(Text, nullable=True, comment="错误信息")
    error_type = Column(
        String(50),
        nullable=True,
        comment="错误类型: SAFE_AUDIT / QUALITY_FAIL / PERF_DEGRADE / LOGIC_ERROR",
    )

    # 关联
    harness_run_rel = relationship("HarnessRun", back_populates="tool_calls")

    # 索引
    __table_args__ = (
        Index("idx_tool_run", "harness_run_id"),
        Index("idx_tool_name", "tool_name"),
        Index("idx_tool_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ToolCallLog(id={self.id}, tool={self.tool_name}, status={self.status})>"


class Skill(BaseModel, Base):
    """
    技能文件
    存储 AI 学到的技能模板，用于优化后续生成
    """

    __tablename__ = "skills"

    name = Column(String(200), unique=True, nullable=False, comment="Skill 名称")
    trigger_conditions = Column(JSONB, nullable=False, comment="触发条件（学科、主题、年龄、难度等）")
    version = Column(Integer, default=1, server_default="1", comment="版本号")
    content = Column(Text, nullable=False, comment="Skill 内容（Markdown）")
    success_count = Column(Integer, default=0, server_default="0", comment="使用成功次数")
    failure_count = Column(Integer, default=0, server_default="0", comment="使用失败次数")
    last_used_at = Column(DateTime(timezone=True), nullable=True, comment="最后使用时间")
    quality_score_avg = Column(Float, nullable=True, comment="平均质量得分")
    is_active = Column(Boolean, default=True, server_default="true", comment="是否启用")

    # 索引
    __table_args__ = (
        Index("idx_skill_trigger", "trigger_conditions", postgresql_using="gin"),
        Index("idx_skill_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name={self.name}, version={self.version})>"


class SessionMemory(BaseModel, Base):
    """
    会话记忆
    存储 AI 在会话中积累的记忆（错误模式、偏好、质量洞察等）
    """

    __tablename__ = "session_memories"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户 ID",
    )
    memory_type = Column(
        String(50),
        nullable=False,
        comment="记忆类型: error_pattern / preference / quality_insight / behavior_pattern",
    )
    content = Column(Text, nullable=False, comment="结构化记忆内容")
    confidence = Column(Float, nullable=False, comment="置信度 (0-1)")
    ttl_days = Column(Integer, default=90, server_default="90", comment="生存天数")
    related_topic = Column(String(200), nullable=True, comment="关联主题")
    expires_at = Column(DateTime(timezone=True), nullable=False, comment="过期时间")
    is_expired = Column(Boolean, default=False, server_default="false", comment="是否已过期")

    # 索引
    __table_args__ = (
        Index("idx_memory_user", "user_id"),
        Index("idx_memory_topic", "related_topic"),
        Index("idx_memory_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<SessionMemory(id={self.id}, type={self.memory_type})>"


class ErrorLog(BaseModel, Base):
    """
    错误日志
    记录 AI 调用链中的错误信息，用于审计和进化
    """

    __tablename__ = "error_logs"

    harness_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("harness_runs.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联的 Harness 执行",
    )
    agent_name = Column(String(100), nullable=False, comment="出错 Agent 名称")
    step_name = Column(String(50), nullable=False, comment="步骤名称")
    error_type = Column(
        String(50),
        nullable=False,
        comment="错误类型: SAFE_AUDIT / QUALITY_FAIL / PERF_DEGRADE / LOGIC_ERROR",
    )
    error_code = Column(String(10), nullable=False, comment="错误编码 (E001-E399)")
    severity = Column(
        String(10),
        nullable=False,
        comment="严重度: P0 / P1 / P2",
    )
    raw_error = Column(Text, nullable=False, comment="原始错误信息")
    context = Column(JSONB, nullable=True, comment="错误上下文")
    affected_output = Column(JSONB, nullable=True, comment="受影响的输出")
    routing_target = Column(String(100), nullable=True, comment="路由目标 Agent")
    auto_fix_attempted = Column(
        Boolean,
        default=False,
        server_default="false",
        comment="是否尝试自动修复",
    )

    # 索引
    __table_args__ = (
        Index("idx_error_type", "error_type"),
        Index("idx_error_severity", "severity"),
        Index("idx_error_agent", "agent_name"),
        Index("idx_error_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ErrorLog(id={self.id}, type={self.error_type}, severity={self.severity})>"


class EvolutionRecord(BaseModel, Base):
    """
    进化记录
    记录 AI 系统的自我进化事件（Skill 创建/更新、记忆清理、策略调整等）
    """

    __tablename__ = "evolution_records"

    evolution_type = Column(
        String(50),
        nullable=False,
        comment="进化类型: skill_created / skill_updated / memory_cleaned / strategy_changed",
    )
    trigger_reason = Column(Text, nullable=False, comment="触发原因")
    target_name = Column(String(200), nullable=False, comment="目标名称")
    change_content = Column(JSONB, nullable=False, comment="变更内容")
    before_snapshot = Column(JSONB, nullable=True, comment="变更前快照")
    after_snapshot = Column(JSONB, nullable=True, comment="变更后快照")
    quality_before = Column(Float, nullable=True, comment="变更前质量分")
    quality_after = Column(Float, nullable=True, comment="变更后质量分")
    rolled_back = Column(
        Boolean,
        default=False,
        server_default="false",
        comment="是否已回滚",
    )

    # 索引
    __table_args__ = (
        Index("idx_evo_type", "evolution_type"),
        Index("idx_evo_target", "target_name"),
        Index("idx_evo_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EvolutionRecord(id={self.id}, type={self.evolution_type})>"
