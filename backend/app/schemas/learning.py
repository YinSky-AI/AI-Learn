# -*- coding: utf-8 -*-
"""
学习相关 Schema
定义学习会话、答题记录等数据结构
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LearningSessionCreate(BaseModel):
    """创建学习会话请求"""
    knowledge_node_id: UUID = Field(..., description="知识点 ID")
    difficulty_level: str = Field(..., description="难度等级")


class LearningSessionResponse(BaseModel):
    """学习会话响应"""
    id: UUID
    user_id: UUID
    knowledge_node_id: UUID
    difficulty_level: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    correct_count: int
    total_questions: int
    created_at: str

    model_config = {"from_attributes": True}


class AnswerSubmit(BaseModel):
    """提交答案请求"""
    question_id: UUID = Field(..., description="题目 ID")
    user_answer: str = Field(..., description="用户答案")
    time_spent_seconds: int = Field(..., ge=0, description="答题用时（秒）")


class AnswerResponse(BaseModel):
    """答题记录响应"""
    id: UUID
    session_id: UUID
    question_id: UUID
    user_answer: str
    is_correct: bool
    time_spent_seconds: int
    answered_at: str

    model_config = {"from_attributes": True}


class AnswerResult(BaseModel):
    """答题结果（含解析）"""
    id: UUID
    is_correct: bool
    correct_answer: str
    explanation: Optional[str] = None
    time_spent_seconds: int

    model_config = {"from_attributes": True}


class SessionCompleteRequest(BaseModel):
    """完成学习会话请求"""
    session_id: UUID = Field(..., description="会话 ID")


class SessionStats(BaseModel):
    """学习会话统计"""
    session_id: UUID
    status: str
    correct_count: int
    total_questions: int
    accuracy_rate: float = Field(..., description="正确率")
    total_time_seconds: int = Field(..., description="总用时")
