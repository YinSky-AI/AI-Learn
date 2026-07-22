# -*- coding: utf-8 -*-
"""
内容相关 Pydantic Schema 模块

定义知识点（KnowledgeNode）、学科（Subject）、年龄分级（AgeGroup）
和题目（Question）的请求/响应数据模型。

该模块支撑教学内容管理和 AI 自适应学习的内容查询：
- 年龄分级和学科的枚举数据响应
- 知识点的详情、列表和筛选
- 题目的详情（含答案）和简要展示（不含答案）
"""

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.services.question_access import sanitize_public_value


# ============ 年龄分级 ============

class AgeGroupResponse(BaseModel):
    """
    年龄分级响应模型

    返回年龄分级的完整信息，包含主题配置（颜色、字号、间距等 UI 参数）。
    """
    code: str
    name: str
    min_age: int
    max_age: int
    theme_config: Any

    model_config = {"from_attributes": True}


class SubjectResponse(BaseModel):
    """
    学科响应模型

    返回学科的基础信息和排序权重，用于前端导航和筛选展示。
    """
    code: str
    name: str
    icon: Optional[str] = None
    sort_order: int

    model_config = {"from_attributes": True}


class KnowledgeNodeResponse(BaseModel):
    """
    知识点详情响应模型

    返回知识点的完整信息，包含内容主体和前置依赖列表。
    """
    id: UUID
    title: str
    description: Optional[str] = None
    subject_code: str
    age_group_code: str
    difficulty_level: str
    content_type: str
    content_body: str
    estimated_minutes: int
    prerequisites: Optional[List[UUID]] = None
    sort_order: int
    is_active: bool
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class KnowledgeNodeBrief(BaseModel):
    """
    知识点简要信息模型（列表展示用）

    用于知识点列表接口，仅包含展示所需的摘要字段，不含内容主体。
    """
    id: UUID
    title: str
    difficulty_level: str
    content_type: str
    estimated_minutes: int
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class KnowledgeNodeFilter(BaseModel):
    """
    知识点筛选条件模型

    用于知识点列表接口的多维度筛选，所有字段均为可选，支持组合查询。
    """
    subject_code: Optional[str] = Field(None, description="学科编码")
    age_group_code: Optional[str] = Field(None, description="年龄分级编码")
    difficulty_level: Optional[str] = Field(None, description="难度等级")
    content_type: Optional[str] = Field(None, description="内容类型")
    keyword: Optional[str] = Field(None, description="搜索关键词")


class OptionItem(BaseModel):
    """
    选择题选项模型

    定义选择题的单个选项结构，包含选项标识（key）和选项内容（value）。
    """
    key: str = Field(..., description="选项标识 (A/B/C/D)")
    value: str = Field(..., description="选项内容")


class QuestionResponse(BaseModel):
    """
    题目详情响应模型

    返回题目的完整信息，包含选项、正确答案和解析。
    用于题目管理后台和错题回顾等需要查看答案的场景。
    """
    id: UUID
    knowledge_node_id: Optional[UUID] = None
    difficulty_level: str
    question_type: str
    question_body: str
    options: Optional[List[OptionItem]] = None
    correct_answer: str
    explanation: Optional[str] = None
    standard_time_seconds: int
    sort_order: int

    model_config = {"from_attributes": True}


class QuestionBrief(BaseModel):
    """
    题目简要信息模型（不含答案，用于答题展示）

    用于学习会话中的题目展示，刻意排除正确答案和解析，
    防止前端泄露答案信息。
    """
    id: UUID
    knowledge_node_id: Optional[UUID] = None
    difficulty_level: str
    question_type: str
    question_body: str
    options: Optional[List[dict[str, Any]]] = None
    standard_time_seconds: int
    sort_order: Optional[int] = None

    model_config = {"from_attributes": True}

    @field_validator("options", mode="before")
    @classmethod
    def sanitize_options(cls, value):
        return sanitize_public_value(value)


class KnowledgePracticeResponse(BaseModel):
    """知识图谱专项练习；题目使用 QuestionBrief，绝不下发答案与解析。"""

    graph_node_id: str
    knowledge_node_id: UUID
    name: str
    subject: str
    difficulty_level: str
    questions: List[QuestionBrief]


class QuestionFilter(BaseModel):
    """
    题目筛选条件模型

    用于题目列表和查询接口，支持按知识点、难度和题型筛选。
    """
    knowledge_node_id: Optional[UUID] = Field(None, description="知识点 ID")
    difficulty_level: Optional[str] = Field(None, description="难度等级")
    question_type: Optional[str] = Field(None, description="题型")
