# -*- coding: utf-8 -*-
"""
服务层包初始化模块

集中暴露课程服务中的高频函数，便于 API 层通过 `from app.services import ...` 统一引用。
当前主要暴露课程查询、用户课程关联、课时完成、AI 对话历史等函数。

Note:
    此处的暴露列表服务于 API 层的便捷导入，各模块仍可直接引用具体服务文件。
"""

from app.services.course_service import (
    list_courses,
    get_course_detail,
    get_lessons_by_course,
    get_or_create_user_course,
    update_course_progress,
    complete_lesson,
    get_user_courses,
    save_chat_message,
    get_chat_history,
)

__all__ = [
    "list_courses",
    "get_course_detail",
    "get_lessons_by_course",
    "get_or_create_user_course",
    "update_course_progress",
    "complete_lesson",
    "get_user_courses",
    "save_chat_message",
    "get_chat_history",
]
