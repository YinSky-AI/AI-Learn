# -*- coding: utf-8 -*-
"""
服务层包初始化
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
