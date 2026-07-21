# -*- coding: utf-8 -*-
"""
课程公开 API 模块

提供无需认证即可访问的课程相关接口，包括课程列表、课程详情、课时列表。
课程详情与课时列表支持可选认证：已登录用户会额外返回各课时的完成状态。

主要功能：
    - 分页课程列表（支持学科、难度、年龄段、关键词筛选）
    - 课程详情查询（支持 UUID 或 slug 访问）
    - 课时列表查询（支持 UUID 或 slug 访问）
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id_optional
from app.models.course import UserLesson
from app.schemas.common import ApiResponse, paged_response, success_response
from app.schemas.content import QuestionBrief
from app.schemas.course import CourseBrief, CourseDetail, LessonBrief
from app.services import content_service, course_service

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_courses(
    subject: Optional[str] = Query(None, description="学科"),
    difficulty: Optional[str] = Query(None, description="难度"),
    age_group: Optional[str] = Query(None, description="年龄段"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """
    课程列表接口（分页 + 多条件筛选）

    公开接口，无需登录。支持按学科、难度、年龄段、关键词筛选，默认每页 20 条。

    Args:
        subject (Optional[str]): 学科编码筛选
        difficulty (Optional[str]): 难度等级筛选
        age_group (Optional[str]): 年龄段编码筛选
        keyword (Optional[str]): 标题或描述关键词搜索
        page (int): 页码，从 1 开始
        page_size (int): 每页数量，默认 20，最大 100
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 分页课程列表（CourseBrief 概要信息）
    """
    # 调用课程服务查询分页结果
    result = await course_service.list_courses(
        db,
        subject=subject,
        difficulty=difficulty,
        age_group=age_group,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    # 将 ORM 对象转换为响应模型
    items = [CourseBrief.model_validate(item) for item in result["items"]]
    return paged_response(
        data=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{course_id}", response_model=ApiResponse)
async def get_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """
    课程详情接口

    支持通过 UUID 或 slug 查询课程详情。已登录用户额外返回各课时的完成状态。

    Args:
        course_id (str): 课程 ID（UUID）或 slug
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 当前登录用户 ID（可选认证）

    Returns:
        ApiResponse: 课程详情（含课时列表及可选的完成状态）
    """
    # 查询课程详情（含课时列表）
    course = await course_service.get_course_detail(db, course_id)
    if course is None:
        return ApiResponse(code="BIZ_001", message="课程不存在", data=None)

    data = CourseDetail.model_validate(course)

    # 已登录用户：查询课时完成状态并合并到响应数据
    if user_id and data.lessons:
        lesson_ids = [str(l.id) for l in data.lessons]
        stmt = select(UserLesson).where(
            UserLesson.user_id == user_id,
            UserLesson.lesson_id.in_(lesson_ids),
            UserLesson.completed == True,
        )
        result = await db.execute(stmt)
        completed_lesson_ids = {str(ul.lesson_id) for ul in result.scalars().all()}

        # 将完成状态标记到每个课时对象
        for lesson in data.lessons:
            lesson.completed = str(lesson.id) in completed_lesson_ids

    return success_response(
        data=data,
        message="获取课程详情成功",
    )


@router.get("/{course_id}/lessons", response_model=ApiResponse)
async def list_lessons(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """
    课时列表接口

    查询指定课程下的所有课时，支持 UUID 或 slug 访问。已登录用户额外返回完成状态。

    Args:
        course_id (str): 课程 ID（UUID）或 slug
        db (AsyncSession): 异步数据库会话
        user_id (Optional[str]): 当前登录用户 ID（可选认证）

    Returns:
        ApiResponse: 课时列表（含可选的完成状态）
    """
    # 获取课程下所有课时
    lessons = await course_service.get_lessons_by_course(db, course_id)
    data = [LessonBrief.model_validate(lesson) for lesson in lessons]

    # 已登录用户：批量查询各课时的完成状态并合并
    if user_id and data:
        lesson_ids = [str(l.id) for l in data]
        stmt = select(UserLesson).where(
            UserLesson.user_id == user_id,
            UserLesson.lesson_id.in_(lesson_ids),
            UserLesson.completed == True,
        )
        result = await db.execute(stmt)
        completed_lesson_ids = {str(ul.lesson_id) for ul in result.scalars().all()}

        # 标记完成状态
        for lesson in data:
            lesson.completed = str(lesson.id) in completed_lesson_ids

    return success_response(
        data=data,
        message="获取课时列表成功",
    )


@router.get("/{course_id}/lessons/{lesson_id}/quiz", response_model=ApiResponse)
async def get_lesson_quiz(
    course_id: str,
    lesson_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    课时测验题目接口

    查询指定课时的测验题目列表。仅当课时类型为 quiz 且已绑定知识点时返回题目。
    返回的题目列表不含正确答案和解析，用于前端答题展示。

    Args:
        course_id (str): 课程 ID（UUID）或 slug
        lesson_id (str): 课时 ID（UUID）
        db (AsyncSession): 异步数据库会话

    Returns:
        ApiResponse: 题目列表（QuestionBrief，不含答案和解析）
    """
    # 校验课程是否存在
    course = await course_service.get_course_by_id(db, course_id)
    if course is None:
        return ApiResponse(code="BIZ_001", message="课程不存在", data=None)

    # 查询课时并校验是否属于该课程
    lesson = await course_service.get_lesson_by_id(db, lesson_id)
    if lesson is None:
        return ApiResponse(code="BIZ_001", message="课时不存在", data=None)
    if str(lesson.course_id) != str(course.id):
        return ApiResponse(code="BIZ_001", message="该课时不属于指定课程", data=None)
    if lesson.type != "quiz":
        return ApiResponse(code="BIZ_001", message="该课时不是测验课时", data=None)

    # 未绑定知识点则返回空列表
    if lesson.knowledge_node_id is None:
        return success_response(data=[], message="该课时未绑定知识点")

    # 获取知识点下的题目列表
    questions = await content_service.list_questions_by_node(
        db,
        lesson.knowledge_node_id,
        local_only=True,
    )
    # 单次课时测验固定最多 10 题，避免把整个知识点题库一次性推给用户。
    data = [QuestionBrief.model_validate(q) for q in questions[:10]]

    return success_response(
        data=data,
        message="获取测验题目成功",
    )
