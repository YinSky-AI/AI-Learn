# -*- coding: utf-8 -*-
"""
AI 出题相关 Schema
定义题目生成请求/响应数据结构
"""

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionGenerateRequest(BaseModel):
    """AI 出题请求"""
    age_group_code: str = Field(..., description="年龄分级编码")
    subject_code: str = Field(..., description="学科编码")
    course_topic: str = Field(..., min_length=1, max_length=200, description="课程主题")
    difficulty_level: str = Field(..., description="难度等级")
    question_types: List[str] = Field(..., min_length=1, description="题型列表")
    question_count: int = Field(..., ge=1, le=20, description="生成数量")
    learning_goal: Optional[str] = Field(None, max_length=200, description="学习目标")


class GeneratedQuestionResponse(BaseModel):
    """生成的题目响应"""
    id: UUID
    batch_id: UUID
    subject_code: str
    course_topic: str
    difficulty_level: str
    question_type: str
    question_body: str
    options: Optional[List[dict]] = None
    correct_answer: str
    explanation: str
    knowledge_tags: Any
    quality_status: str
    created_at: str

    model_config = {"from_attributes": True}


class BatchQueryRequest(BaseModel):
    """批次查询请求"""
    subject_code: Optional[str] = Field(None, description="学科筛选")
    status: Optional[str] = Field(None, description="状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class BatchResponse(BaseModel):
    """生成批次响应"""
    id: UUID
    user_id: UUID
    age_group_code: str
    subject_code: str
    course_topic: str
    difficulty_level: str
    question_types: Any
    question_count: int
    learning_goal: Optional[str] = None
    status: str
    prompt_version: str
    created_at: str

    model_config = {"from_attributes": True}


class VariantRequest(BaseModel):
    """变式题生成请求"""
    question_id: UUID = Field(..., description="原题目 ID")
    difficulty_level: Optional[str] = Field(None, description="目标难度（不指定则保持原难度）")


class QuestionHistoryFilter(BaseModel):
    """历史题目筛选"""
    subject_code: Optional[str] = Field(None, description="学科")
    course_topic: Optional[str] = Field(None, description="课程主题")
    difficulty_level: Optional[str] = Field(None, description="难度")
    quality_status: Optional[str] = Field(None, description="质量状态")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class GenerateResultResponse(BaseModel):
    """生成结果汇总"""
    batch_id: UUID
    status: str
    total_generated: int
    passed_count: int
    failed_count: int
    questions: List[GeneratedQuestionResponse] = []


class QualityCheckResponse(BaseModel):
    """质量检查结果"""
    question_id: UUID
    checks: List[dict] = Field(default_factory=list, description="各项检查结果")
    overall_status: str = Field(..., description="整体状态")
