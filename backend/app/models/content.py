# -*- coding: utf-8 -*-
"""
内容相关模型
包含 AgeGroup、Subject、KnowledgeNode、Question
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
    AGE_06_09 / AGE_10_12 / AGE_13_15 / AGE_16_18
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
    SUBJ_MATH / SUBJ_CHINESE / SUBJ_ENGLISH / ...
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
    树状结构，关联学科和年龄分级
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
    教材题库中的预置题目
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
