# -*- coding: utf-8 -*-
"""
课程相关 Pydantic Schema 模块

定义课程（Course）、课时（Lesson）、用户课程关联（UserCourse）、
用户课时记录（UserLesson）和 AI 对话消息（ChatMessage）的完整数据结构。

Schema 设计模式：
- Base: 共享字段的基类模型
- Create: 创建请求模型（POST）
- Update: 更新请求模型（PATCH/PUT），所有字段可选
- Brief: 列表展示用简要信息
- Detail: 详情展示用完整信息
- Response: 响应模型，通常包含关联对象
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============ Course ============

class CourseBase(BaseModel):
    """
    课程基础信息模型

    定义课程的共享字段，被 CourseCreate 继承，也可作为其他 Schema 的嵌套字段。
    """
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
    """
    创建课程请求模型

    继承 CourseBase，包含创建课程所需的全部必填字段。
    """
    pass


class CourseUpdate(BaseModel):
    """
    更新课程请求模型

    所有字段均为可选，用于 PATCH 方式的部分更新。
    仅提供需要修改的字段，未提供的字段保持原值不变。
    """
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
    """
    课程简要信息模型（列表展示用）

    用于课程列表接口，包含展示所需的摘要信息，不含详情和课时列表。
    model_config 启用 from_attributes 以支持 ORM 对象直接转换。
    """
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
    """
    课程详情模型（含课时列表）

    继承 CourseBrief，额外包含课程描述和关联的课时简要列表。
    用于课程详情接口的完整信息展示。
    """
    description: Optional[str] = None
    lessons: List["LessonBrief"] = []

    model_config = {"from_attributes": True}


# ============ Lesson ============

class LessonBase(BaseModel):
    """
    课时基础信息模型

    定义课时的共享字段，被 LessonCreate 继承。
    """
    title: str = Field(..., description="课时标题")
    description: Optional[str] = Field(None, description="课时描述")
    type: str = Field(..., description="类型: video/text/interactive/quiz/game")
    duration: int = Field(default=0, description="课时时长（分钟）")
    order: int = Field(default=0, description="课时顺序")
    content: Optional[str] = Field(None, description="课时内容")
    is_active: bool = Field(default=True, description="是否启用")


class LessonCreate(LessonBase):
    """
    创建课时请求模型

    继承 LessonBase，额外包含所属课程 ID。
    """
    course_id: UUID = Field(..., description="所属课程 ID")


class LessonUpdate(BaseModel):
    """
    更新课时请求模型

    所有字段均为可选，支持 PATCH 部分更新。
    """
    title: Optional[str] = Field(None, description="课时标题")
    description: Optional[str] = Field(None, description="课时描述")
    type: Optional[str] = Field(None, description="类型")
    duration: Optional[int] = Field(None, description="课时时长（分钟）")
    order: Optional[int] = Field(None, description="课时顺序")
    content: Optional[str] = Field(None, description="课时内容")
    is_active: Optional[bool] = Field(None, description="是否启用")


class LessonBrief(BaseModel):
    """
    课时简要信息模型

    用于课程详情中的课时列表展示，包含当前用户的完成状态（仅当请求带认证时有效）。
    """
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
    """
    课时详情模型

    继承 LessonBrief，额外包含课时内容（富文本/Markdown）。
    """
    content: Optional[str] = None

    model_config = {"from_attributes": True}


# ============ UserCourse ============

class UserCourseBase(BaseModel):
    """
    用户课程基础信息模型

    定义用户课程关联的共享字段，被 UserCourseCreate 继承。
    """
    progress: int = Field(default=0, description="学习进度（0-100）")
    completed_lessons: int = Field(default=0, description="已完成课时数")
    status: str = Field(default="enrolled", description="状态: enrolled/completed")


class UserCourseCreate(UserCourseBase):
    """
    创建用户课程记录请求模型

    继承 UserCourseBase，额外包含用户 ID 和课程 ID。
    """
    user_id: UUID = Field(..., description="用户 ID")
    course_id: UUID = Field(..., description="课程 ID")


class UserCourseUpdate(BaseModel):
    """
    更新用户课程记录请求模型

    所有字段均为可选，支持学习进度、完成课时数和状态的增量更新。
    """
    progress: Optional[int] = Field(None, description="学习进度（0-100）")
    completed_lessons: Optional[int] = Field(None, description="已完成课时数")
    status: Optional[str] = Field(None, description="状态")
    last_accessed_at: Optional[datetime] = Field(None, description="最近学习时间")


class UserCourseResponse(BaseModel):
    """
    用户课程响应模型

    返回用户课程学习记录的完整信息，包含嵌套的课程简要信息。
    """
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
    """
    用户课时基础信息模型

    定义用户课时完成记录的共享字段。
    """
    completed: bool = Field(default=False, description="是否已完成")
    time_spent_seconds: int = Field(default=0, description="学习用时（秒）")


class UserLessonCreate(UserLessonBase):
    """
    创建用户课时记录请求模型

    继承 UserLessonBase，额外包含用户 ID、课时 ID 和课程 ID。
    """
    user_id: UUID = Field(..., description="用户 ID")
    lesson_id: UUID = Field(..., description="课时 ID")
    course_id: UUID = Field(..., description="课程 ID")


class UserLessonUpdate(BaseModel):
    """
    更新用户课时记录请求模型

    支持更新完成状态、完成时间和学习用时。
    """
    completed: Optional[bool] = Field(None, description="是否已完成")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    time_spent_seconds: Optional[int] = Field(None, description="学习用时（秒）")


class UserLessonResponse(BaseModel):
    """
    用户课时响应模型

    返回用户课时完成记录的完整信息，包含嵌套的课时简要信息。
    """
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
    """
    AI 对话消息基础信息模型

    定义对话消息的共享字段，被 ChatMessageCreate 继承。
    """
    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="消息内容")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class ChatMessageCreate(ChatMessageBase):
    """
    创建对话消息请求模型

    继承 ChatMessageBase，支持关联到用户、课程和课时上下文。
    """
    user_id: Optional[str] = Field(None, description="用户 ID")
    course_id: Optional[str] = Field(None, description="课程 ID")
    lesson_id: Optional[str] = Field(None, description="课时 ID")


class ChatMessageResponse(BaseModel):
    """
    对话消息响应模型

    返回对话消息的完整信息，包含关联的课程和课时上下文。
    """
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
    """
    课程筛选条件模型

    用于课程列表接口的查询参数封装，所有字段均为可选，支持组合筛选。
    """
    subject: Optional[str] = Field(None, description="学科")
    difficulty: Optional[str] = Field(None, description="难度")
    age_group: Optional[str] = Field(None, description="年龄段")
    keyword: Optional[str] = Field(None, description="搜索关键词")
