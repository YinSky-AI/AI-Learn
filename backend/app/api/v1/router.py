# -*- coding: utf-8 -*-
"""
v1 版本路由注册
将所有 v1 子路由注册到统一前缀下
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.content import router as content_router
from app.api.v1.learning import router as learning_router
from app.api.v1.questions import router as questions_router
from app.api.v1.ai import router as ai_router
from app.api.v1.achievement import router as achievement_router
from app.api.v1.progress import router as progress_router
from app.api.v1.courses import router as courses_router
from app.api.v1.user_courses import router as user_courses_router

# v1 总路由
router = APIRouter()

# 注册各模块路由
router.include_router(auth_router, prefix="/auth", tags=["认证"])
router.include_router(users_router, prefix="/users", tags=["用户管理"])
router.include_router(content_router, prefix="/content", tags=["内容管理"])
router.include_router(learning_router, prefix="/learning", tags=["学习"])
router.include_router(questions_router, prefix="/questions", tags=["AI出题"])
router.include_router(ai_router, prefix="/ai", tags=["AI助手"])
router.include_router(achievement_router, prefix="/achievements", tags=["成就"])
router.include_router(progress_router, prefix="/progress", tags=["进度"])
router.include_router(courses_router, prefix="/courses", tags=["课程"])
router.include_router(user_courses_router, prefix="/user", tags=["用户课程"])
