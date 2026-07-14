# -*- coding: utf-8 -*-
"""
AI 出题相关 Pydantic Schema 模块

定义 AI 题目生成流程中的请求和响应数据模型，包括：
- 题目生成请求（QuestionGenerateRequest）
- 生成结果响应（GeneratedQuestionResponse、GenerateResultResponse）
- 批次查询（BatchQueryRequest、BatchResponse）
- 变式题生成（VariantRequest）
- 历史题目筛选（QuestionHistoryFilter）
- 质量检查（QualityCheckResponse）

这些 Schema 支撑 AI 自适应学习的题目生成、质量评估和历史管理功能。
"""

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionGenerateRequest(BaseModel):
    """
    AI 出题请求模型

    用户请求 AI 生成题目时提交，包含学科、主题、难度、题型和数量等参数。
    系统根据这些参数调用 DeepSeek API 生成符合要求的练习题。
    """
    age_group_code: str = Field(..., description="年龄分级编码")
    subject_code: str = Field(..., description="学科编码")
    course_topic: str = Field(..., min_length=1, max_length=200, description="课程主题")
    difficulty_level: str = Field(..., description="难度等级")
    question_types: List[str] = Field(..., min_length=1, description="题型列表")
    question_count: int = Field(..., ge=1, le=20, description="生成数量")
    learning_goal: Optional[str] = Field(None, max_length=200, description="学习目标")


class GeneratedQuestionResponse(BaseModel):
    """
    生成的题目响应模型

    返回 AI 生成题目的完整信息，包含题干、选项、答案、解析和质量状态。
    """
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
    """
    生成批次查询请求模型

    用于查询历史生成批次列表，支持按学科和状态筛选及分页。
    """
    subject_code: Optional[str] = Field(None, description="学科筛选")
    status: Optional[str] = Field(None, description="状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class BatchResponse(BaseModel):
    """
    生成批次响应模型

    返回生成批次的摘要信息，不含具体的题目列表。
    """
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
    """
    变式题生成请求模型

    基于已有题目生成难度相同或不同的变式题，用于错题巩固和进阶练习。
    """
    question_id: UUID = Field(..., description="原题目 ID")
    difficulty_level: Optional[str] = Field(None, description="目标难度（不指定则保持原难度）")


class QuestionHistoryFilter(BaseModel):
    """
    历史题目筛选模型

    用于查询 AI 生成历史题目库，支持多维度组合筛选和分页。
    """
    subject_code: Optional[str] = Field(None, description="学科")
    course_topic: Optional[str] = Field(None, description="课程主题")
    difficulty_level: Optional[str] = Field(None, description="难度")
    quality_status: Optional[str] = Field(None, description="质量状态")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class GenerateResultResponse(BaseModel):
    """
    生成结果汇总模型

    AI 题目生成完成后返回的汇总信息，包含批次状态、生成总数、通过数、失败数
    和题目详情列表。
    """
    batch_id: UUID
    status: str
    total_generated: int
    passed_count: int
    failed_count: int
    questions: List[GeneratedQuestionResponse] = []


class QualityCheckResponse(BaseModel):
    """
    质量检查结果模型

    返回单道题目的多维度质量检查结果和整体状态判定。
    """
    question_id: UUID
    checks: List[dict] = Field(default_factory=list, description="各项检查结果")
    overall_status: str = Field(..., description="整体状态")
