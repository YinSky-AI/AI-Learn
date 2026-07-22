# -*- coding: utf-8 -*-
"""
v1 版本 API 路由总入口

本模块负责聚合并注册所有 v1 版本的子路由模块，统一挂载到 /api/v1 前缀下。
包含的模块：认证、用户管理、课程、内容、学习、进度、AI出题、成就、AI助手、用户课程。

 Attributes:
     router (APIRouter): FastAPI 路由聚合器，供主应用 include_router 使用。
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
from app.api.v1.wrong_book import router as wrong_book_router
from app.api.v1.behavior import router as behavior_router
from app.api.v1.daily_challenge import router as daily_challenge_router
from app.api.v1.knowledge_graph import router as knowledge_graph_router

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
router.include_router(wrong_book_router, prefix="/wrong-book", tags=["错题本"])
router.include_router(knowledge_graph_router, prefix="/knowledge-graph", tags=["knowledge-graph"])
router.include_router(behavior_router, prefix="/user/behavior", tags=["学习行为"])
router.include_router(daily_challenge_router, prefix="/challenge", tags=["daily-challenge"])
