# -*- coding: utf-8 -*-
"""
课程相关 Schema
定义 Course、Lesson、UserCourse、UserLesson、ChatMessage 的数据结构
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============ Course ============

class CourseBase(BaseModel):
    """课程基础信息"""
    title: str = Field(..., description="课程标题")
    description: Optional[str] = Field(None, description="课程描述")
    subject: str = Field(..., description="学科")
    age_group: str = Field(..., description="年龄段")
    difficulty: str = Field(..., description="难度")
    duration: int = Field(default=0, description="课程总时长（分钟）")
    image_url: Optional[str] = Field(None, description="封面图 URL")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    total_lessons: int = Field(default=0, description="总课时数")
    is_active: bool = Field(default=True, description="是否启用")
    sort_order: int = Field(default=0, description="排序权重")


class CourseCreate(CourseBase):
    """创建课程请求"""
    pass


class CourseUpdate(BaseModel):
    """更新课程请求"""
    title: Optional[str] = Field(None, description="课程标题")
    description: Optional[str] = Field(None, description="课程描述")
    subject: Optional[str] = Field(None, description="学科")
    age_group: Optional[str] = Field(None, description="年龄段")
    difficulty: Optional[str] = Field(None, description="难度")
    duration: Optional[int] = Field(None, description="课程总时长（分钟）")
    image_url: Optional[str] = Field(None, description="封面图 URL")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    total_lessons: Optional[int] = Field(None, description="总课时数")
    is_active: Optional[bool] = Field(None, description="是否启用")
    sort_order: Optional[int] = Field(None, description="排序权重")


class CourseBrief(BaseModel):
    """课程简要信息（列表展示用）"""
    id: UUID
    slug: Optional[str] = None
    title: str
    subject: str
    age_group: str
    difficulty: str
    duration: int
    rating: float
    enroll_count: int
    image_url: Optional[str] = None
    total_lessons: int
    tags: Optional[List[str]] = None
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class CourseDetail(CourseBrief):
    """课程详情（含课时列表）"""
    description: Optional[str] = None
    lessons: List["LessonBrief"] = []

    model_config = {"from_attributes": True}


# ============ Lesson ============

class LessonBase(BaseModel):
    """课时基础信息"""
    title: str = Field(..., description="课时标题")
    description: Optional[str] = Field(None, description="课时描述")
    type: str = Field(..., description="类型: video/text/interactive/quiz/game")
    duration: int = Field(default=0, description="课时时长（分钟）")
    order: int = Field(default=0, description="课时顺序")
    content: Optional[str] = Field(None, description="课时内容")
    is_active: bool = Field(default=True, description="是否启用")


class LessonCreate(LessonBase):
    """创建课时请求"""
    course_id: UUID = Field(..., description="所属课程 ID")


class LessonUpdate(BaseModel):
    """更新课时请求"""
    title: Optional[str] = Field(None, description="课时标题")
    description: Optional[str] = Field(None, description="课时描述")
    type: Optional[str] = Field(None, description="类型")
    duration: Optional[int] = Field(None, description="课时时长（分钟）")
    order: Optional[int] = Field(None, description="课时顺序")
    content: Optional[str] = Field(None, description="课时内容")
    is_active: Optional[bool] = Field(None, description="是否启用")


class LessonBrief(BaseModel):
    """课时简要信息"""
    id: UUID
    course_id: UUID
    title: str
    description: Optional[str] = None
    type: str
    duration: int
    order: int
    is_active: bool
    completed: Optional[bool] = Field(default=False, description="当前用户是否已完成（仅当请求带认证时有效）")

    model_config = {"from_attributes": True}


class LessonDetail(LessonBrief):
    """课时详情"""
    content: Optional[str] = None

    model_config = {"from_attributes": True}


# ============ UserCourse ============

class UserCourseBase(BaseModel):
    """用户课程基础信息"""
    progress: int = Field(default=0, description="学习进度（0-100）")
    completed_lessons: int = Field(default=0, description="已完成课时数")
    status: str = Field(default="enrolled", description="状态: enrolled/completed")


class UserCourseCreate(UserCourseBase):
    """创建用户课程记录请求"""
    user_id: UUID = Field(..., description="用户 ID")
    course_id: UUID = Field(..., description="课程 ID")


class UserCourseUpdate(BaseModel):
    """更新用户课程记录请求"""
    progress: Optional[int] = Field(None, description="学习进度（0-100）")
    completed_lessons: Optional[int] = Field(None, description="已完成课时数")
    status: Optional[str] = Field(None, description="状态")
    last_accessed_at: Optional[datetime] = Field(None, description="最近学习时间")


class UserCourseResponse(BaseModel):
    """用户课程响应"""
    id: UUID
    user_id: UUID
    course_id: UUID
    progress: int
    completed_lessons: int
    enrolled_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    status: str
    course: Optional[CourseBrief] = None

    model_config = {"from_attributes": True}


# ============ UserLesson ============

class UserLessonBase(BaseModel):
    """用户课时基础信息"""
    completed: bool = Field(default=False, description="是否已完成")
    time_spent_seconds: int = Field(default=0, description="学习用时（秒）")


class UserLessonCreate(UserLessonBase):
    """创建用户课时记录请求"""
    user_id: UUID = Field(..., description="用户 ID")
    lesson_id: UUID = Field(..., description="课时 ID")
    course_id: UUID = Field(..., description="课程 ID")


class UserLessonUpdate(BaseModel):
    """更新用户课时记录请求"""
    completed: Optional[bool] = Field(None, description="是否已完成")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    time_spent_seconds: Optional[int] = Field(None, description="学习用时（秒）")


class UserLessonResponse(BaseModel):
    """用户课时响应"""
    id: UUID
    user_id: UUID
    lesson_id: UUID
    course_id: UUID
    completed: bool
    completed_at: Optional[datetime] = None
    time_spent_seconds: int
    lesson: Optional[LessonBrief] = None

    model_config = {"from_attributes": True}


# ============ ChatMessage ============

class ChatMessageBase(BaseModel):
    """AI 对话消息基础信息"""
    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="消息内容")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class ChatMessageCreate(ChatMessageBase):
    """创建对话消息请求"""
    user_id: Optional[str] = Field(None, description="用户 ID")
    course_id: Optional[str] = Field(None, description="课程 ID")
    lesson_id: Optional[str] = Field(None, description="课时 ID")


class ChatMessageResponse(BaseModel):
    """对话消息响应"""
    id: UUID
    user_id: Optional[UUID] = None
    course_id: Optional[UUID] = None
    lesson_id: Optional[UUID] = None
    role: str
    content: str
    context: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ============ Filter / Query ============

class CourseFilter(BaseModel):
    """课程筛选条件"""
    subject: Optional[str] = Field(None, description="学科")
    difficulty: Optional[str] = Field(None, description="难度")
    age_group: Optional[str] = Field(None, description="年龄段")
    keyword: Optional[str] = Field(None, description="搜索关键词")
