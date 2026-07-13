# -*- coding: utf-8 -*-
"""
内容相关 Schema
定义知识点、学科、年龄分级、题目等数据结构
"""

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============ 年龄分级 ============

class AgeGroupResponse(BaseModel):
    """年龄分级响应"""
    code: str
    name: str
    min_age: int
    max_age: int
    theme_config: Any

    model_config = {"from_attributes": True}


# ============ 学科 ============

class SubjectResponse(BaseModel):
    """学科响应"""
    code: str
    name: str
    icon: Optional[str] = None
    sort_order: int

    model_config = {"from_attributes": True}


# ============ 知识点 ============

class KnowledgeNodeResponse(BaseModel):
    """知识点响应"""
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
    """知识点简要信息（列表展示用）"""
    id: UUID
    title: str
    difficulty_level: str
    content_type: str
    estimated_minutes: int
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class KnowledgeNodeFilter(BaseModel):
    """知识点筛选条件"""
    subject_code: Optional[str] = Field(None, description="学科编码")
    age_group_code: Optional[str] = Field(None, description="年龄分级编码")
    difficulty_level: Optional[str] = Field(None, description="难度等级")
    content_type: Optional[str] = Field(None, description="内容类型")
    keyword: Optional[str] = Field(None, description="搜索关键词")


# ============ 题目 ============

class OptionItem(BaseModel):
    """选择题选项"""
    key: str = Field(..., description="选项标识 (A/B/C/D)")
    value: str = Field(..., description="选项内容")


class QuestionResponse(BaseModel):
    """题目响应"""
    id: UUID
    knowledge_node_id: UUID
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
    """题目简要信息（不含答案，用于答题展示）"""
    id: UUID
    difficulty_level: str
    question_type: str
    question_body: str
    options: Optional[List[OptionItem]] = None
    standard_time_seconds: int

    model_config = {"from_attributes": True}


class QuestionFilter(BaseModel):
    """题目筛选条件"""
    knowledge_node_id: Optional[UUID] = Field(None, description="知识点 ID")
    difficulty_level: Optional[str] = Field(None, description="难度等级")
    question_type: Optional[str] = Field(None, description="题型")
