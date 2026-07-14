# -*- coding: utf-8 -*-
"""
学习相关 Pydantic Schema 模块

定义学习会话（LearningSession）和答题记录（Answer）的完整数据结构，
支撑平台的自适应学习核心交互流程。

包含的数据模型：
- 学习会话创建和响应
- 答案提交和结果返回
- 会话完成和统计
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LearningSessionCreate(BaseModel):
    """
    创建学习会话请求模型

    用户开始学习某个知识点时提交，指定知识点 ID 和希望学习的难度等级。
    """
    knowledge_node_id: UUID = Field(..., description="知识点 ID")
    difficulty_level: str = Field(..., description="难度等级")


class LearningSessionResponse(BaseModel):
    """
    学习会话响应模型

    返回学习会话的完整信息，包含状态、答题统计和时间戳。
    """
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
    """
    提交答案请求模型

    用户在学习会话中回答某道题目时提交，包含题目 ID、用户答案和答题用时。
    time_spent_seconds 必须大于等于 0。
    """
    question_id: UUID = Field(..., description="题目 ID")
    user_answer: str = Field(..., description="用户答案")
    time_spent_seconds: int = Field(..., ge=0, description="答题用时（秒）")


class AnswerResponse(BaseModel):
    """
    答题记录响应模型

    返回答题记录的基本信息，不含正确答案（用于答题历史列表）。
    """
    id: UUID
    session_id: UUID
    question_id: UUID
    user_answer: str
    is_correct: bool
    time_spent_seconds: int
    answered_at: str

    model_config = {"from_attributes": True}


class AnswerResult(BaseModel):
    """
    答题结果模型（含解析）

    用户提交答案后返回的即时结果，包含是否正确、正确答案和解析。
    用于前端即时反馈和错题展示。
    """
    id: UUID
    is_correct: bool
    correct_answer: str
    explanation: Optional[str] = None
    time_spent_seconds: int

    model_config = {"from_attributes": True}


class SessionCompleteRequest(BaseModel):
    """
    完成学习会话请求模型

    用户主动结束或系统自动完成学习会话时提交。
    """
    session_id: UUID = Field(..., description="会话 ID")


class SessionStats(BaseModel):
    """
    学习会话统计模型

    学习会话完成后的汇总统计数据，包含正确率、总用时等核心指标。
    """
    session_id: UUID
    status: str
    correct_count: int
    total_questions: int
    accuracy_rate: float = Field(..., description="正确率")
    total_time_seconds: int = Field(..., description="总用时")
