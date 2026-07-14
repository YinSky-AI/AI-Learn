# -*- coding: utf-8 -*-
"""
内容相关模型定义模块

定义平台的核心教学内容实体，包括年龄分级（AgeGroup）、学科（Subject）、
知识点（KnowledgeNode）和题目（Question）数据模型。

这些模型支撑 AI 自适应学习的内容组织：
- 年龄分级：定义不同年龄段的 UI 主题和学习策略
- 学科：平台支持的学科分类
- 知识点：树状结构的学习内容单元，关联学科和年龄分级
- 题目：与知识点绑定的预置练习题
"""

from sqlalchemy import (
    Column, Float, Integer, String, Text, Boolean, Index, ForeignKey,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import BaseModel
from app.models import Base


class AgeGroup(Base):
    """
    年龄分级模型

    定义平台支持的年龄段分级，每个分级有独立的主题配置（颜色、字号、间距等），
    用于为不同年龄的学生提供差异化的 UI 和学习体验。

    编码规范：AGE_06_09 / AGE_10_12 / AGE_13_15 / AGE_16_18

    Attributes:
        code: 分级编码（主键）
        name: 分级显示名称（如 "小学低年级"）
        min_age: 最小年龄（含）
        max_age: 最大年龄（含）
        theme_config: 主题配置 JSONB（颜色、字号、间距等）
        knowledge_nodes: 关联的知识点列表（一对多）
    """

    __tablename__ = "age_groups"

    code = Column(String(10), primary_key=True, comment="分级编码")
    name = Column(String(50), nullable=False, comment="显示名称")
    min_age = Column(Integer, nullable=False, comment="最小年龄")
    max_age = Column(Integer, nullable=False, comment="最大年龄")
    theme_config = Column(JSONB, nullable=False, comment="主题配置（颜色/字号/间距等）")

    # 关联
    knowledge_nodes = relationship("KnowledgeNode", back_populates="age_group_rel")

    def __repr__(self) -> str:
        return f"<AgeGroup(code={self.code}, name={self.name})>"


class Subject(Base):
    """
    学科模型

    定义平台支持的学科分类，每个学科有唯一的编码和展示名称。

    编码规范：SUBJ_MATH / SUBJ_CHINESE / SUBJ_ENGLISH / ...

    Attributes:
        code: 学科编码（主键）
        name: 学科名称（如 "数学"）
        icon: 学科图标路径
        sort_order: 排序权重，控制前端展示顺序
        knowledge_nodes: 关联的知识点列表（一对多）
    """

    __tablename__ = "subjects"

    code = Column(String(20), primary_key=True, comment="学科编码")
    name = Column(String(50), nullable=False, comment="学科名称")
    icon = Column(String(100), nullable=True, comment="图标路径")
    sort_order = Column(Integer, default=0, server_default="0", comment="排序权重")

    # 关联
    knowledge_nodes = relationship("KnowledgeNode", back_populates="subject_rel")

    def __repr__(self) -> str:
        return f"<Subject(code={self.code}, name={self.name})>"


class KnowledgeNode(BaseModel, Base):
    """
    知识点模型

    平台核心教学内容单元，采用树状结构组织（通过 prerequisites 表达前置依赖）。
    每个知识点关联到具体的学科和年龄分级，包含知识内容主体和推荐的完成时长。

    Attributes:
        title: 知识点标题
        description: 知识点简介
        subject_code: 所属学科编码（外键）
        age_group_code: 适用年龄分级编码（外键）
        difficulty_level: 难度等级（DIFF_EASY / DIFF_MEDIUM / DIFF_HARD）
        content_type: 内容类型（TYPE_READ / TYPE_QUIZ / TYPE_GAME）
        content_body: 知识内容主体（Markdown 格式）
        estimated_minutes: 预计完成时长（分钟，默认 5）
        prerequisites: 前置知识点 ID 列表（UUID 数组）
        sort_order: 排序权重
        is_active: 是否启用
        subject_rel: 关联的学科对象（多对一）
        age_group_rel: 关联的年龄分级对象（多对一）
        questions: 关联的题目列表（一对多）
    """

    __tablename__ = "knowledge_nodes"

    title = Column(String(200), nullable=False, comment="标题")
    description = Column(Text, nullable=True, comment="简介")
    subject_code = Column(
        String(20),
        ForeignKey("subjects.code", ondelete="RESTRICT"),
        nullable=False,
        comment="所属学科",
    )
    age_group_code = Column(
        String(10),
        ForeignKey("age_groups.code", ondelete="RESTRICT"),
        nullable=False,
        comment="适用年龄段",
    )
    difficulty_level = Column(String(10), nullable=False, comment="难度: DIFF_EASY / DIFF_MEDIUM / DIFF_HARD")
    content_type = Column(String(20), nullable=False, comment="类型: TYPE_READ / TYPE_QUIZ / TYPE_GAME")
    content_body = Column(Text, nullable=False, comment="知识内容主体（Markdown）")
    estimated_minutes = Column(Integer, default=5, server_default="5", comment="预计完成时长（分钟）")
    prerequisites = Column(ARRAY(UUID(as_uuid=True)), nullable=True, comment="前置知识点 ID 列表")
    sort_order = Column(Integer, default=0, server_default="0", comment="排序")
    is_active = Column(Boolean, default=True, server_default="true", comment="是否启用")

    # 关联
    subject_rel = relationship("Subject", back_populates="knowledge_nodes")
    age_group_rel = relationship("AgeGroup", back_populates="knowledge_nodes")
    questions = relationship("Question", back_populates="knowledge_node_rel")

    # 索引
    __table_args__ = (
        Index("idx_node_subject", "subject_code"),
        Index("idx_node_age", "age_group_code"),
        Index("idx_node_diff", "difficulty_level"),
        Index("idx_node_type", "content_type"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeNode(id={self.id}, title={self.title})>"


class Question(Base):
    """
    题目模型

    教材题库中的预置练习题，与知识点一对一关联。
    支持选择题（单选/多选）和填空题等多种题型，包含标准答案和解析。

    Attributes:
        id: 题目 UUID（主键）
        knowledge_node_id: 所属知识点 ID（外键，级联删除）
        difficulty_level: 难度等级
        question_type: 题型（CHOICE / MULTIPLE_CHOICE / FILL_BLANK）
        question_body: 题目内容（Markdown 格式）
        options: 选择题选项（JSONB 数组，每项包含 key 和 value）
        correct_answer: 正确答案文本
        explanation: 答案解析
        standard_time_seconds: 标准答题用时（秒，默认 30）
        sort_order: 排序权重
        knowledge_node_rel: 关联的知识点对象（多对一）
    """

    __tablename__ = "questions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="题目 ID",
    )
    knowledge_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属知识点",
    )
    difficulty_level = Column(String(10), nullable=False, comment="难度")
    question_type = Column(String(20), nullable=False, comment="题型: CHOICE / MULTIPLE_CHOICE / FILL_BLANK")
    question_body = Column(Text, nullable=False, comment="题目内容（Markdown）")
    options = Column(JSONB, nullable=True, comment="选择题选项: [{key, value}]")
    correct_answer = Column(Text, nullable=False, comment="正确答案")
    explanation = Column(Text, nullable=True, comment="解析")
    standard_time_seconds = Column(Integer, default=30, server_default="30", comment="标准答题用时（秒）")
    sort_order = Column(Integer, default=0, server_default="0", comment="排序")

    # 关联
    knowledge_node_rel = relationship("KnowledgeNode", back_populates="questions")

    # 索引
    __table_args__ = (
        Index("idx_question_node", "knowledge_node_id"),
        Index("idx_question_diff", "difficulty_level"),
    )

    def __repr__(self) -> str:
        return f"<Question(id={self.id}, type={self.question_type})>"
