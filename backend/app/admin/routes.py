# -*- coding: utf-8 -*-
"""
管理后台路由模块

提供后台管理系统专用的 API 接口，包括运营数据看板、系统健康检查、AI 审查等。
当前为占位实现，预留后台管理扩展点。

主要功能：
    - 获取管理后台仪表盘摘要数据
    - 系统健康状态检查
    - AI 审查记录查询
"""

import hmac
import hashlib
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from app.core.database import AI_LearnAsyncSessionLocal
from app.services.admin_auth import (
    CSRF_COOKIE_NAME,
    LOGIN_CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
)
from app.services.admin_changes import AdminChangeService

router = APIRouter(prefix="/admin", tags=["管理后台"])

# 兼容旧依赖名，但统一复用 core 中受启动版本检查覆盖的题库 Session。
AiLearnSessionLocal = AI_LearnAsyncSessionLocal

SUBJECT_MAP = {
    "math": "数学",
    "chinese": "语文",
    "english": "英语",
    "science": "科学",
    "history": "历史",
    "programming": "编程",
    "art": "美术",
}

# ============ Jinja2 模板环境 ============

TEMPLATE_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


# ============ 数据库依赖 ============

async def get_db():
    """
    管理后台数据库依赖

    为管理后台路由提供异步数据库会话，自动处理提交与回滚。
    """
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_ai_learn_db():
    """
    题库数据库依赖（ai_learn 库）

    为题库管理 API 提供独立的数据库会话，连接到 ai_learn 数据库。
    """
    async with AiLearnSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ============ Session 验证 ============

def _check_session(request: Request):
    """
    HTML 页面会话检查

    中间件已完成签名、过期、撤销和角色复核；此处仅保留路由级纵深防御。
    """
    if not getattr(request.state, "admin_principal", None):
        return RedirectResponse(url="/admin/login", status_code=302)
    return None


def _check_api_auth(request: Request):
    """
    API 端点会话验证

    中间件已完成统一授权；此处仅防止路由被脱离应用单独挂载后失守。
    """
    if not getattr(request.state, "admin_principal", None):
        return PlainTextResponse("未登录或会话已过期", status_code=401)
    return None


async def _apply_admin_change(request: Request, db: AsyncSession, entity_type: str, entity_id: str, action: str):
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        result = await AdminChangeService(db).change(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=request.state.admin_principal.user_id,
            reason=str(body.get("reason", "")),
            request_id=getattr(request.state, "request_id", "unassigned"),
        )
    except ValueError as exc:
        return PlainTextResponse(str(exc), status_code=400)
    if not result.changed:
        status_code = 404 if result.message == "目标不存在" else 409
        return PlainTextResponse(result.message, status_code=status_code)
    return JSONResponse(
        status_code=200,
        content={"success": result.changed, "message": result.message, "impact_scope": result.impact_scope},
    )


# ============ 登录 / 登出 ============

def _login_response(request: Request, error: str = "", status_code: int = 200):
    service = request.app.state.admin_auth_service
    csrf_token = secrets.token_urlsafe(32)
    template = jinja_env.get_template("login.html")
    response = HTMLResponse(
        template.render(error=error, csrf_token=csrf_token),
        status_code=status_code,
    )
    response.set_cookie(
        LOGIN_CSRF_COOKIE_NAME,
        csrf_token,
        max_age=600,
        secure=service.cookie_secure,
        httponly=True,
        samesite="strict",
        path="/admin/login",
    )
    return response


def _login_identifier_fingerprint(identifier: str) -> str:
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()[:12]


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """
    管理后台登录页面

    渲染基于 Jinja2 模板的登录页面。

    Args:
        error (str): 登录错误提示信息

    Returns:
        HTMLResponse: 登录页面 HTML
    """
    return _login_response(request, error)


@router.post("/login")
async def login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    """
    管理后台登录提交

    校验登录 CSRF、平台管理员账号与密码，成功后创建可撤销签名会话。

    Args:
        password (str): 提交的密码

    Returns:
        RedirectResponse: 登录成功重定向到仪表盘，失败返回登录页
    """
    cookie_csrf = request.cookies.get(LOGIN_CSRF_COOKIE_NAME, "")
    if not cookie_csrf or not hmac.compare_digest(cookie_csrf, csrf_token):
        return PlainTextResponse("安全校验失败，请刷新页面后重试", status_code=403)

    service = request.app.state.admin_auth_service
    request_id = getattr(request.state, "request_id", "unassigned")
    identifier_fingerprint = _login_identifier_fingerprint(identifier)
    try:
        user = await service.authenticate(identifier, password)
    except Exception as exc:
        logger.bind(audit_event="admin_login_unavailable").error(
            "admin_audit event=admin_login_unavailable identifier_fingerprint={} "
            "request_id={} error_type={}",
            identifier_fingerprint,
            request_id,
            type(exc).__name__,
        )
        return _login_response(request, "登录服务暂不可用，请稍后重试", status_code=503)
    if user is None:
        logger.bind(audit_event="admin_login_rejected").warning(
            "admin_audit event=admin_login_rejected identifier_fingerprint={} "
            "request_id={}",
            identifier_fingerprint,
            request_id,
        )
        return _login_response(request, "账号或密码错误", status_code=401)

    try:
        issued = await service.create_session(user)
    except Exception as exc:
        logger.bind(audit_event="admin_login_unavailable").error(
            "admin_audit event=admin_login_unavailable actor_id={} request_id={} "
            "error_type={}",
            user.id,
            request_id,
            type(exc).__name__,
        )
        return _login_response(request, "登录服务暂不可用，请稍后重试", status_code=503)
    logger.bind(audit_event="admin_login_succeeded").info(
        "admin_audit event=admin_login_succeeded actor_id={} request_id={}",
        user.id,
        request_id,
    )
    response = RedirectResponse(url="/admin", status_code=302)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        issued.token,
        max_age=service.session_ttl_seconds,
        secure=service.cookie_secure,
        httponly=True,
        samesite="strict",
        path="/admin",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        issued.csrf_token,
        max_age=service.session_ttl_seconds,
        secure=service.cookie_secure,
        httponly=False,
        samesite="strict",
        path="/admin",
    )
    response.delete_cookie(LOGIN_CSRF_COOKIE_NAME, path="/admin/login")
    return response


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    """
    管理后台退出登录

    校验会话绑定的 CSRF，服务端撤销会话后清除 Cookie。

    Returns:
        RedirectResponse: 重定向到登录页
    """
    principal = getattr(request.state, "admin_principal", None)
    if principal is None or not hmac.compare_digest(principal.csrf_token, csrf_token):
        return PlainTextResponse("安全校验失败，请刷新页面后重试", status_code=403)
    service = request.app.state.admin_auth_service
    await service.revoke_session(request.cookies.get(SESSION_COOKIE_NAME))
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/admin")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/admin")
    return response


# ============ 仪表盘 ============

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """
    管理后台仪表盘页面

    聚合展示关键运营数据：总用户数、总课程数、总学习时长、完成课时数、
    课程报名排行 TOP 10、学科分布等。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        HTMLResponse: 渲染后的仪表盘页面
    """
    redirect = _check_session(request)
    if redirect:
        return redirect

    # 总用户数
    total_users = (await db.execute(
        text("SELECT COUNT(*) FROM public.users WHERE deleted_at IS NULL")
    )).scalar()

    # 总课程数
    total_courses = (await db.execute(
        text("SELECT COUNT(*) FROM public.courses WHERE deleted_at IS NULL")
    )).scalar()

    # 总学习时长（秒）
    total_seconds = int(
        (await db.execute(
            text("SELECT COALESCE(SUM(time_spent_seconds), 0) FROM public.user_lessons")
        )).scalar()
    )
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    total_time_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"

    # 总完成课时数
    completed_lessons = (await db.execute(
        text("SELECT COUNT(*) FROM public.user_lessons WHERE completed = true")
    )).scalar()

    # 课程报名排行 TOP 10
    top_rows = (await db.execute(text(
        "SELECT title, subject, enroll_count, rating "
        "FROM public.courses WHERE deleted_at IS NULL ORDER BY enroll_count DESC NULLS LAST LIMIT 10"
    ))).fetchall()

    top_courses = []
    for row in top_rows:
        top_courses.append({
            "title": row[0],
            "subject": SUBJECT_MAP.get(row[1], row[1] or "未知"),
            "enroll_count": row[2] or 0,
            "rating": row[3],
        })

    # 学科分布
    subject_rows = (await db.execute(text(
        "SELECT subject, COUNT(*) AS cnt "
        "FROM public.courses WHERE deleted_at IS NULL GROUP BY subject ORDER BY cnt DESC"
    ))).fetchall()

    max_count = subject_rows[0][1] if subject_rows else 1
    subject_dist = []
    for row in subject_rows:
        subject_dist.append({
            "subject": SUBJECT_MAP.get(row[0], row[0] or "未知"),
            "count": row[1],
            "percent": round(row[1] / max_count * 100) if max_count > 0 else 0,
        })

    template = jinja_env.get_template("dashboard.html")
    return HTMLResponse(template.render(
        active_page="dashboard",
        stats={
            "total_users": total_users or 0,
            "total_courses": total_courses or 0,
            "total_time": total_time_str,
            "completed_lessons": completed_lessons or 0,
        },
        top_courses=top_courses,
        subject_dist=subject_dist,
    ))


# ============ 课程管理页面 ============

@router.get("/courses", response_class=HTMLResponse)
async def courses_page(request: Request, db: AsyncSession = Depends(get_db)):
    """
    课程管理页面

    渲染课程列表管理页面，需登录后方可访问。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        HTMLResponse: 课程管理页面 HTML
    """
    redirect = _check_session(request)
    if redirect:
        return redirect
    template = jinja_env.get_template("courses.html")
    return HTMLResponse(template.render(active_page="courses"))


# ============ 课程 API ============

@router.get("/courses/api/list")
async def courses_api_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    title: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    is_active: Optional[str] = Query(None),
    state: str = Query("active", pattern="^(active|deleted)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
):
    """
    课程列表 API（后台管理）

    分页查询课程列表，支持按标题、学科、难度、启用状态筛选。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话
        title (Optional[str]): 标题关键词筛选
        subject (Optional[str]): 学科筛选
        difficulty (Optional[str]): 难度筛选
        is_active (Optional[str]): 启用状态筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 15

    Returns:
        dict: 分页课程列表
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    conditions = ["deleted_at IS NOT NULL" if state == "deleted" else "deleted_at IS NULL"]
    params: dict = {}

    # 动态构建筛选条件
    if title:
        conditions.append("title ILIKE :title")
        params["title"] = f"%{title}%"
    if subject:
        conditions.append("subject = :subject")
        params["subject"] = subject
    if difficulty:
        conditions.append("difficulty = :difficulty")
        params["difficulty"] = difficulty
    if is_active is not None:
        conditions.append("is_active = :is_active")
        params["is_active"] = is_active.lower() == "true"

    where = " AND ".join(conditions) if conditions else "TRUE"

    # 查询总数
    total = (await db.execute(
        text(f"SELECT COUNT(*) FROM public.courses WHERE {where}"), params
    )).scalar()

    # 分页数据
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    data_sql = (
        "SELECT id, title, description, subject, difficulty, age_group, duration, "
        "rating, enroll_count, image_url, total_lessons, tags, is_active, "
        "sort_order, slug, created_at, updated_at "
        f"FROM public.courses WHERE {where} "
        "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    )
    rows = (await db.execute(text(data_sql), params)).fetchall()

    items = []
    for row in rows:
        items.append({
            "id": str(row[0]),
            "title": row[1],
            "description": row[2],
            "subject": row[3],
            "difficulty": row[4],
            "age_group": row[5],
            "duration": row[6],
            "rating": float(row[7]) if row[7] is not None else None,
            "enroll_count": row[8] or 0,
            "image_url": row[9],
            "total_lessons": row[10],
            "tags": row[11],
            "is_active": row[12],
            "sort_order": row[13],
            "slug": row[14],
            "created_at": row[15].isoformat() if row[15] else None,
            "updated_at": row[16].isoformat() if row[16] else None,
        })

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/courses/api/{course_id}")
async def course_detail_api(
    course_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    获取单个课程信息 API（课时管理页用）

    Args:
        course_id (str): 课程 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        JSONResponse: 课程详情或错误信息
    """
    auth = _check_api_auth(request)
    if auth:
        return auth
    try:
        result = await db.execute(
            text(
                "SELECT id, title, subject, difficulty, age_group, total_lessons, is_active "
                "FROM courses WHERE id = :id AND deleted_at IS NULL"
            ),
            {"id": course_id}
        )
        row = result.fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"success": False, "message": "课程不存在"})
        return JSONResponse(content={
            "success": True,
            "data": {
                "id": str(row[0]),
                "title": row[1],
                "subject": row[2],
                "difficulty": row[3],
                "age_group": row[4],
                "total_lessons": row[5],
                "is_active": row[6],
            }
        })
    except Exception:
        return PlainTextResponse("课程信息查询失败", status_code=500)


@router.put("/courses/api/{course_id}/status")
async def course_status_api(
    course_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    修改课程启用/停用状态

    Args:
        course_id (str): 课程 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    new_status = body.get("is_active")
    if new_status is None:
        return JSONResponse(status_code=400, content={"success": False, "message": "缺少 is_active 参数"})

    await db.execute(
        text(
            "UPDATE public.courses SET is_active = :is_active, updated_at = NOW() "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"is_active": new_status, "id": course_id},
    )

    return {"success": True, "message": "状态已更新"}


@router.delete("/courses/api/{course_id}")
async def course_delete_api(
    course_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    删除课程（同时清理关联数据）

    按依赖顺序清理 user_lessons、user_courses、lessons 关联数据后删除课程。

    Args:
        course_id (str): 课程 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    return await _apply_admin_change(request, db, "course", course_id, "soft_delete")


@router.post("/courses/api/{course_id}/restore")
async def course_restore_api(course_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await _apply_admin_change(request, db, "course", course_id, "restore")


# ============ 课时管理页面 ============

@router.get("/lessons", response_class=HTMLResponse)
async def lessons_page(request: Request, course_id: Optional[str] = Query(None)):
    """
    课时管理页面

    渲染课时列表管理页面，支持传入课程 ID 进行筛选。

    Args:
        request (Request): FastAPI 请求对象
        course_id (Optional[str]): 课程 ID

    Returns:
        HTMLResponse: 课时管理页面 HTML
    """
    redirect = _check_session(request)
    if redirect:
        return redirect
    template = jinja_env.get_template("lessons.html")
    return HTMLResponse(template.render(active_page="lessons", course_id=course_id))


# ============ 用户管理页面 ============

@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: AsyncSession = Depends(get_db)):
    """
    用户管理页面

    渲染用户列表管理页面，需登录后方可访问。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        HTMLResponse: 用户管理页面 HTML
    """
    redirect = _check_session(request)
    if redirect:
        return redirect
    template = jinja_env.get_template("users.html")
    return HTMLResponse(template.render(active_page="users"))


@router.get("/recovery", response_class=HTMLResponse)
async def recovery_page(request: Request):
    """集中展示可恢复对象，避免管理员必须预先保存对象 ID。"""
    redirect = _check_session(request)
    if redirect:
        return redirect
    template = jinja_env.get_template("recovery.html")
    return HTMLResponse(template.render(active_page="recovery"))


# ============ 用户 API ============

@router.get("/users/api/list")
async def users_api_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    keyword: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    state: str = Query("active", pattern="^(active|deleted)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
):
    """
    用户列表 API（后台管理）

    分页查询用户列表，支持按昵称/邮箱关键词和年龄段筛选。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话
        keyword (Optional[str]): 昵称或邮箱关键词
        age_group (Optional[str]): 年龄段筛选
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 15

    Returns:
        dict: 分页用户列表
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    conditions = ["deleted_at IS NOT NULL" if state == "deleted" else "deleted_at IS NULL"]
    params: dict = {}

    # 动态构建筛选条件
    if keyword:
        conditions.append("(nickname ILIKE :kw OR email ILIKE :kw)")
        params["kw"] = f"%{keyword}%"
    if age_group:
        conditions.append("age_group = :ag")
        params["ag"] = age_group

    where = " AND ".join(conditions)

    # 查询总数
    total = (await db.execute(
        text(f"SELECT COUNT(*) FROM public.users WHERE {where}"), params
    )).scalar()

    # 分页数据
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    data_sql = (
        "SELECT id, nickname, email, age_group, total_score, streak_days, "
        "last_login_date, created_at "
        f"FROM public.users WHERE {where} "
        "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    )
    rows = (await db.execute(text(data_sql), params)).fetchall()

    items = []
    for row in rows:
        items.append({
            "id": str(row[0]),
            "nickname": row[1],
            "email": row[2],
            "age_group": row[3],
            "total_score": row[4] or 0,
            "streak_days": row[5] or 0,
            "last_login_date": row[6].isoformat() if row[6] else None,
            "created_at": row[7].isoformat() if row[7] else None,
        })

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.put("/users/api/{user_id}")
async def user_update_api(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    修改用户信息（昵称、年龄段）

    Args:
        user_id (str): 用户 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    nickname = body.get("nickname")
    age_group = body.get("age_group")

    if nickname is None and age_group is None:
        return JSONResponse(status_code=400, content={"success": False, "message": "至少需要修改一个字段"})

    # 动态构建更新字段
    updates = []
    params: dict = {"id": user_id}

    if nickname is not None:
        updates.append("nickname = :nickname")
        params["nickname"] = nickname
    if age_group is not None:
        updates.append("age_group = :age_group")
        params["age_group"] = age_group if age_group else None

    updates.append("updated_at = NOW()")

    sql = f"UPDATE public.users SET {', '.join(updates)} WHERE id = :id AND deleted_at IS NULL"
    result = await db.execute(text(sql), params)

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "用户不存在"})

    return {"success": True, "message": "用户已更新"}


@router.delete("/users/api/{user_id}")
async def user_delete_api(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    删除用户（同时清理关联数据）

    按依赖顺序清理 user_lessons、user_courses 关联数据后删除用户。

    Args:
        user_id (str): 用户 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    return await _apply_admin_change(request, db, "user", user_id, "soft_delete")


@router.post("/users/api/{user_id}/restore")
async def user_restore_api(user_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await _apply_admin_change(request, db, "user", user_id, "restore")


# ============ 课程创建 API ============

@router.post("/courses/api/create")
async def course_create_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    创建课程

    接收课程基本信息，自动生成 UUID 并插入数据库。
    tags 字段支持逗号分隔字符串或数组，会自动转换为 JSON 数组存储。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 创建结果（含新课程 ID）
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    import uuid, json

    course_id = str(uuid.uuid4())

    title = body.get("title")
    if not title:
        return JSONResponse(status_code=400, content={"success": False, "message": "缺少必填字段 title"})

    # 处理 tags：前端传逗号分隔字符串，数据库存 JSON 数组
    tags_raw = body.get("tags")
    tags_value = None
    if tags_raw:
        if isinstance(tags_raw, str):
            tags_value = json.dumps([t.strip() for t in tags_raw.split(",") if t.strip()])
        elif isinstance(tags_raw, list):
            tags_value = json.dumps(tags_raw)
        else:
            tags_value = json.dumps([str(tags_raw)])

    try:
        await db.execute(
            text(
                "INSERT INTO public.courses (id, title, description, subject, difficulty, age_group, "
                "duration, rating, enroll_count, total_lessons, image_url, tags, is_active, sort_order, slug) "
                "VALUES (:id, :title, :description, :subject, :difficulty, :age_group, "
                ":duration, :rating, :enroll_count, :total_lessons, :image_url, :tags, :is_active, :sort_order, :slug)"
            ),
            {
                "id": course_id,
                "title": title,
                "description": body.get("description"),
                "subject": body.get("subject"),
                "difficulty": body.get("difficulty"),
                "age_group": body.get("age_group"),
                "duration": body.get("duration") or 0,
                "rating": body.get("rating") or 4.0,
                "enroll_count": 0,
                "total_lessons": 0,
                "image_url": body.get("image_url"),
                "tags": tags_value,
                "is_active": body.get("is_active", True),
                "sort_order": body.get("sort_order") or 0,
                "slug": body.get("slug") or None,
            },
        )
    except Exception:
        return PlainTextResponse("课程创建失败", status_code=500)

    return {"success": True, "message": "课程已创建", "id": course_id}


# ============ 课程编辑 API ============

@router.put("/courses/api/{course_id}")
async def course_update_api(
    course_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    编辑课程（动态更新提供的字段）

    仅更新请求体中显式提供的允许字段，tags 字段支持字符串或数组自动转换。

    Args:
        course_id (str): 课程 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    allowed_fields = [
        "title", "description", "subject", "difficulty", "age_group",
        "duration", "image_url", "is_active", "sort_order", "slug",
    ]
    updates = []
    params: dict = {"id": course_id}

    # 动态构建允许字段的更新
    for field in allowed_fields:
        if field in body:
            updates.append(f"{field} = :{field}")
            # slug 空字符串转 None，避免唯一约束冲突
            params[field] = body[field] if body[field] != "" else None

    # tags 需要特殊处理（字符串 -> JSON 数组）
    if "tags" in body:
        tags_raw = body["tags"]
        if tags_raw:
            if isinstance(tags_raw, str):
                params["tags"] = json.dumps([t.strip() for t in tags_raw.split(",") if t.strip()])
            elif isinstance(tags_raw, list):
                params["tags"] = json.dumps(tags_raw)
            else:
                params["tags"] = json.dumps([str(tags_raw)])
        else:
            params["tags"] = None
        updates.append("tags = :tags")

    if not updates:
        return JSONResponse(status_code=400, content={"success": False, "message": "没有需要更新的字段"})

    updates.append("updated_at = NOW()")

    sql = f"UPDATE public.courses SET {', '.join(updates)} WHERE id = :id AND deleted_at IS NULL"
    result = await db.execute(text(sql), params)

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "课程不存在"})

    return {"success": True, "message": "课程已更新"}


# ============ 课时列表 API ============

@router.get("/lessons/api/list")
async def lessons_api_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    course_id: Optional[str] = Query(None),
    state: str = Query("active", pattern="^(active|deleted)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    课时列表 API（后台管理）

    分页查询指定课程下的课时列表，按 order 排序。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话
        course_id (str): 课程 ID（必填）
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 50

    Returns:
        dict: 分页课时列表
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    if state == "active" and not course_id:
        return PlainTextResponse("课程 ID 不能为空", status_code=400)
    conditions = ["deleted_at IS NOT NULL" if state == "deleted" else "deleted_at IS NULL"]
    params: dict = {}
    if course_id:
        conditions.append("course_id = :course_id")
        params["course_id"] = course_id
    where = " AND ".join(conditions)

    # 查询总数
    total = (await db.execute(
        text(f"SELECT COUNT(*) FROM public.lessons WHERE {where}"),
        params,
    )).scalar()

    # 分页数据
    offset = (page - 1) * page_size
    rows = (await db.execute(
        text(
            'SELECT id, course_id, title, description, type, duration, "order", '
            "content, is_active, created_at "
            f"FROM public.lessons WHERE {where} "
            'ORDER BY "order" LIMIT :limit OFFSET :offset'
        ),
        {**params, "limit": page_size, "offset": offset},
    )).fetchall()

    items = []
    for row in rows:
        items.append({
            "id": str(row[0]),
            "course_id": str(row[1]),
            "title": row[2],
            "description": row[3],
            "type": row[4],
            "duration": row[5],
            "order": row[6],
            "content": row[7],
            "is_active": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
        })

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


# ============ 课时创建 API ============

@router.post("/lessons/api/create")
async def lesson_create_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    创建课时

    在指定课程下创建新课时，并自动更新课程的 total_lessons 计数。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 创建结果（含新课时 ID）
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    course_id = body.get("course_id")
    if not course_id:
        return JSONResponse(status_code=400, content={"success": False, "message": "缺少必填字段 course_id"})

    import uuid

    lesson_id = str(uuid.uuid4())

    course_exists = (await db.execute(
        text("SELECT 1 FROM public.courses WHERE id = :id AND deleted_at IS NULL"),
        {"id": course_id},
    )).scalar_one_or_none()
    if course_exists is None:
        return PlainTextResponse("课程不存在或已移入可恢复状态", status_code=404)

    try:
        await db.execute(
            text(
                'INSERT INTO public.lessons (id, course_id, title, description, type, duration, "order", content, is_active) '
                'VALUES (:id, :course_id, :title, :description, :type, :duration, :order, :content, :is_active)'
            ),
            {
                "id": lesson_id,
                "course_id": course_id,
                "title": body.get("title"),
                "description": body.get("description"),
                "type": body.get("type"),
                "duration": body.get("duration"),
                "order": body.get("order", 0),
                "content": body.get("content"),
                "is_active": body.get("is_active", True),
            },
        )

        # 更新课程的 total_lessons 计数
        await db.execute(
            text(
                "UPDATE public.courses SET total_lessons = ("
                "SELECT COUNT(*) FROM public.lessons "
                "WHERE course_id = :id AND is_active = true AND deleted_at IS NULL"
                "), updated_at = NOW() WHERE id = :id"
            ),
            {"id": course_id},
        )
    except Exception:
        return PlainTextResponse("课时创建失败", status_code=500)

    return {"success": True, "message": "课时已创建", "id": lesson_id}


# ============ 课时编辑 API ============

@router.put("/lessons/api/{lesson_id}")
async def lesson_update_api(
    lesson_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    编辑课时（动态更新提供的字段）

    仅更新请求体中显式提供的允许字段。
    若修改了 order 或 is_active，会自动重新计算所属课程的 total_lessons。

    Args:
        lesson_id (str): 课时 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    allowed_fields = ["course_id", "title", "description", "type", "duration", "order", "content", "is_active"]
    updates = []
    params: dict = {"id": lesson_id}

    # 动态构建允许字段的更新（order 为 PostgreSQL 保留字，需加双引号）
    for field in allowed_fields:
        if field in body:
            col = f'"{field}"' if field == "order" else field
            updates.append(f"{col} = :{field}")
            params[field] = body[field]

    if not updates:
        return JSONResponse(status_code=400, content={"success": False, "message": "没有需要更新的字段"})

    original_course_id = (await db.execute(
        text("SELECT course_id FROM public.lessons WHERE id=:id AND deleted_at IS NULL FOR UPDATE"),
        {"id": lesson_id},
    )).scalar_one_or_none()
    if original_course_id is None:
        return PlainTextResponse("课时不存在", status_code=404)
    if "course_id" in body:
        target_course = (await db.execute(
            text("SELECT id FROM public.courses WHERE id=:id AND deleted_at IS NULL"),
            {"id": body["course_id"]},
        )).scalar_one_or_none()
        if target_course is None:
            return PlainTextResponse("目标课程不存在或已移入可恢复状态", status_code=400)

    updates.append("updated_at = NOW()")

    sql = f"UPDATE public.lessons SET {', '.join(updates)} WHERE id = :id AND deleted_at IS NULL"
    result = await db.execute(text(sql), params)

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "课时不存在"})

    # 移动、排序或启停课时时，同时维护旧课程与新课程的活动课时计数。
    if {"course_id", "order", "is_active"}.intersection(body):
        affected_course_ids = {str(original_course_id), str(body.get("course_id", original_course_id))}
        for affected_course_id in affected_course_ids:
            await db.execute(
                text(
                    "UPDATE public.courses SET total_lessons = ("
                    "SELECT COUNT(*) FROM public.lessons "
                    "WHERE course_id = :cid AND is_active = true AND deleted_at IS NULL"
                    "), updated_at = NOW() WHERE id = :cid"
                ),
                {"cid": affected_course_id},
            )

    return {"success": True, "message": "课时已更新"}


# ============ 课时删除 API ============

@router.delete("/lessons/api/{lesson_id}")
async def lesson_delete_api(
    lesson_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    删除课时（同时清理关联数据）

    清理 user_lessons、chat_messages 关联数据后删除课时，并更新所属课程的 total_lessons 计数。

    Args:
        lesson_id (str): 课时 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    return await _apply_admin_change(request, db, "lesson", lesson_id, "soft_delete")


@router.post("/lessons/api/{lesson_id}/restore")
async def lesson_restore_api(lesson_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await _apply_admin_change(request, db, "lesson", lesson_id, "restore")


# ============ 课时详情 API ============

@router.get("/lessons/api/{lesson_id}")
async def lesson_detail_api(
    lesson_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    课时详情 API

    查询指定课时的详细信息。

    Args:
        lesson_id (str): 课时 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 课时详情或 404 错误
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    row = (await db.execute(
        text(
            'SELECT id, course_id, title, description, type, duration, "order", '
            "content, is_active, created_at, updated_at "
            "FROM public.lessons WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": lesson_id},
    )).fetchone()

    if not row:
        return JSONResponse(status_code=404, content={"success": False, "message": "课时不存在"})

    return {
        "id": str(row[0]),
        "course_id": str(row[1]),
        "title": row[2],
        "description": row[3],
        "type": row[4],
        "duration": row[5],
        "order": row[6],
        "content": row[7],
        "is_active": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
    }


# ============ 课时批量排序 API ============

@router.put("/lessons/api/reorder")
async def lessons_reorder_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    课时批量排序

    接收课时 ID 与新的排序号列表，批量更新课时顺序。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    items = body.get("items")
    if not items or not isinstance(items, list):
        return JSONResponse(status_code=400, content={"success": False, "message": "缺少 items 参数"})

    try:
        for item in items:
            item_id = item.get("id")
            item_order = item.get("order")
            if item_id is None or item_order is None:
                continue
            await db.execute(
                text(
                    'UPDATE public.lessons SET "order" = :order, updated_at = NOW() '
                    "WHERE id = :id AND deleted_at IS NULL"
                ),
                {"id": item_id, "order": item_order},
            )
    except Exception:
        return PlainTextResponse("课时排序失败", status_code=500)

    return {"success": True, "message": "排序已更新"}


# ============ 题库管理页面 ============

@router.get("/questions", response_class=HTMLResponse)
async def questions_page(request: Request):
    """
    题库管理页面

    渲染题库列表管理页面，需登录后方可访问。

    Args:
        request (Request): FastAPI 请求对象

    Returns:
        HTMLResponse: 题库管理页面 HTML
    """
    redirect = _check_session(request)
    if redirect:
        return redirect
    template = jinja_env.get_template("questions.html")
    return HTMLResponse(template.render(active_page="questions"))


# ============ 题库 API ============

@router.get("/questions/api/list")
async def questions_api_list(
    request: Request,
    db: AsyncSession = Depends(get_ai_learn_db),
    subject: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    question_type: Optional[str] = Query(None, alias="type"),
    keyword: Optional[str] = Query(None),
    state: str = Query("active", pattern="^(active|deleted)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
):
    """
    题库列表 API（后台管理）

    分页查询题目列表，支持按学科、年龄段、难度、题型、关键词筛选。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话
        subject (Optional[str]): 学科筛选
        age_group (Optional[str]): 年龄段筛选
        difficulty (Optional[str]): 难度筛选
        question_type (Optional[str]): 题型筛选
        keyword (Optional[str]): 题干关键词
        page (int): 页码，默认 1
        page_size (int): 每页数量，默认 15

    Returns:
        dict: 分页题目列表
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    conditions = ["deleted_at IS NOT NULL" if state == "deleted" else "deleted_at IS NULL"]
    params: dict = {}

    if subject:
        conditions.append("subject = :subject")
        params["subject"] = subject
    if age_group:
        conditions.append("age_group = :age_group")
        params["age_group"] = age_group
    if difficulty:
        conditions.append("difficulty = :difficulty")
        params["difficulty"] = difficulty
    if question_type:
        conditions.append("type = :qtype")
        params["qtype"] = question_type
    if keyword:
        conditions.append("content ILIKE :kw")
        params["kw"] = f"%{keyword}%"

    where = " AND ".join(conditions)

    total = (await db.execute(
        text(f"SELECT COUNT(*) FROM public.questions WHERE {where}"), params
    )).scalar()

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    data_sql = (
        "SELECT id, subject, age_group, difficulty, grade, content, "
        "options, correct_answer, explanation, type, tags, source, created_at, "
        "language "
        f"FROM public.questions WHERE {where} "
        "ORDER BY id DESC LIMIT :limit OFFSET :offset"
    )
    rows = (await db.execute(text(data_sql), params)).fetchall()

    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "subject": row[1],
            "age_group": row[2],
            "difficulty": row[3],
            "grade": row[4],
            "content": row[5] or "",
            "options": row[6],
            "correct_answer": row[7],
            "explanation": row[8][:100] + "..." if row[8] and len(row[8]) > 100 else (row[8] or ""),
            "type": row[9],
            "tags": row[10],
            "source": row[11],
            "created_at": row[12].isoformat() if row[12] else None,
            "language": row[13],
        })

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/questions/api/{question_id}")
async def question_detail_api(
    question_id: int,
    request: Request,
    db: AsyncSession = Depends(get_ai_learn_db),
):
    """
    题目详情 API

    Args:
        question_id (int): 题目 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        JSONResponse: 题目详情或错误信息
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        row = (await db.execute(
            text(
                "SELECT id, subject, age_group, difficulty, grade, content, "
                "options, correct_answer, explanation, type, tags, source, "
                "language "
                "FROM public.questions WHERE id = :id AND deleted_at IS NULL"
            ),
            {"id": question_id},
        )).fetchone()

        if not row:
            return JSONResponse(status_code=404, content={"success": False, "message": "题目不存在"})

        return JSONResponse(content={
            "success": True,
            "data": {
                "id": row[0],
                "subject": row[1],
                "age_group": row[2],
                "difficulty": row[3],
                "grade": row[4],
                "content": row[5],
                "options": row[6],
                "correct_answer": row[7],
                "explanation": row[8],
                "type": row[9],
                "tags": row[10],
                "source": row[11],
                "language": row[12],
            }
        })
    except Exception:
        return PlainTextResponse("题目信息查询失败", status_code=500)


@router.post("/questions/api/create")
async def question_create_api(
    request: Request,
    db: AsyncSession = Depends(get_ai_learn_db),
):
    """
    创建题目

    接收题目基本信息并插入数据库。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 创建结果（含新题目 ID）
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    content = body.get("content")
    if not content:
        return JSONResponse(status_code=400, content={"success": False, "message": "缺少必填字段 content"})

    options_raw = body.get("options")
    options_value = None
    if options_raw:
        if isinstance(options_raw, list):
            import json
            options_value = json.dumps(options_raw)
        elif isinstance(options_raw, str):
            options_value = options_raw

    tags_raw = body.get("tags")
    tags_value = None
    if tags_raw:
        if isinstance(tags_raw, list):
            tags_value = tags_raw
        elif isinstance(tags_raw, str):
            tags_value = [t.strip() for t in tags_raw.split(",") if t.strip()]

    try:
        result = await db.execute(
            text(
                "INSERT INTO public.questions (subject, age_group, difficulty, grade, content, "
                "options, correct_answer, explanation, type, tags, source) "
                "VALUES (:subject, :age_group, :difficulty, :grade, :content, "
                ":options, :correct_answer, :explanation, :type, :tags, :source) "
                "RETURNING id"
            ),
            {
                "subject": body.get("subject", "math"),
                "age_group": body.get("age_group", "6-8"),
                "difficulty": body.get("difficulty", "beginner"),
                "grade": body.get("grade"),
                "content": content,
                "options": options_value,
                "correct_answer": body.get("correct_answer", ""),
                "explanation": body.get("explanation", ""),
                "type": body.get("type", "single_choice"),
                "tags": tags_value,
                "source": body.get("source", "manual"),
            },
        )
        question_id = result.scalar()
    except Exception:
        return PlainTextResponse("题目创建失败", status_code=500)

    return {"success": True, "message": "题目已创建", "id": question_id}


@router.put("/questions/api/{question_id}")
async def question_update_api(
    question_id: int,
    request: Request,
    db: AsyncSession = Depends(get_ai_learn_db),
):
    """
    编辑题目（动态更新提供的字段）

    Args:
        question_id (int): 题目 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    allowed_fields = [
        "subject", "age_group", "difficulty", "grade",
        "content", "correct_answer", "explanation", "type", "source",
    ]
    updates = []
    params: dict = {"id": question_id}

    for field in allowed_fields:
        if field in body:
            updates.append(f"{field} = :{field}")
            params[field] = body[field]

    # options 需要特殊处理（数组 -> JSON）
    if "options" in body:
        options_raw = body["options"]
        if options_raw:
            if isinstance(options_raw, list):
                import json
                params["options"] = json.dumps(options_raw)
            elif isinstance(options_raw, str):
                params["options"] = options_raw
        else:
            params["options"] = None
        updates.append("options = :options")

    # tags 需要特殊处理（字符串 -> 数组）
    if "tags" in body:
        tags_raw = body["tags"]
        if tags_raw:
            if isinstance(tags_raw, list):
                params["tags"] = tags_raw
            elif isinstance(tags_raw, str):
                params["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            params["tags"] = None
        updates.append("tags = :tags")

    if not updates:
        return JSONResponse(status_code=400, content={"success": False, "message": "没有需要更新的字段"})

    updates.append("created_at = NOW()")

    sql = f"UPDATE public.questions SET {', '.join(updates)} WHERE id = :id AND deleted_at IS NULL"
    result = await db.execute(text(sql), params)

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "题目不存在"})

    return {"success": True, "message": "题目已更新"}


@router.delete("/questions/api/{question_id}")
async def question_delete_api(
    question_id: int,
    request: Request,
    db: AsyncSession = Depends(get_ai_learn_db),
):
    """
    删除题目

    Args:
        question_id (int): 题目 ID
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 操作结果
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    return await _apply_admin_change(request, db, "question", str(question_id), "soft_delete")


@router.post("/questions/api/{question_id}/restore")
async def question_restore_api(question_id: int, request: Request, db: AsyncSession = Depends(get_ai_learn_db)):
    return await _apply_admin_change(request, db, "question", str(question_id), "restore")


@router.post("/questions/api/import")
async def questions_import_api(
    request: Request,
    db: AsyncSession = Depends(get_ai_learn_db),
):
    """
    批量导入题目（JSON 格式）

    接收 JSON 数组，批量插入题目。适用于外部 AI 生成的题库导入。

    Args:
        request (Request): FastAPI 请求对象
        db (AsyncSession): 异步数据库会话

    Returns:
        dict: 导入结果统计
    """
    auth = _check_api_auth(request)
    if auth:
        return auth

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "message": "无效的请求数据"})

    questions = body.get("questions") if isinstance(body, dict) else body
    if not questions or not isinstance(questions, list):
        return JSONResponse(status_code=400, content={"success": False, "message": "缺少 questions 数组"})

    imported = 0
    failed = 0
    errors = []
    import json

    for idx, q in enumerate(questions):
        try:
            content = q.get("content")
            if not content:
                failed += 1
                errors.append({"index": idx, "reason": "content 为空"})
                continue

            options_raw = q.get("options")
            options_value = None
            if options_raw:
                if isinstance(options_raw, list):
                    options_value = json.dumps(options_raw)
                elif isinstance(options_raw, str):
                    options_value = options_raw

            tags_raw = q.get("tags")
            tags_value = None
            if tags_raw:
                if isinstance(tags_raw, list):
                    tags_value = tags_raw
                elif isinstance(tags_raw, str):
                    tags_value = [t.strip() for t in tags_raw.split(",") if t.strip()]

            await db.execute(
                text(
                    "INSERT INTO public.questions (subject, age_group, difficulty, grade, content, "
                    "options, correct_answer, explanation, type, tags, source, batch_id) "
                    "VALUES (:subject, :age_group, :difficulty, :grade, :content, "
                    ":options, :correct_answer, :explanation, :type, :tags, :source, :batch_id)"
                ),
                {
                    "subject": q.get("subject", "math"),
                    "age_group": q.get("age_group", "6-8"),
                    "difficulty": q.get("difficulty", "beginner"),
                    "grade": q.get("grade"),
                    "content": content,
                    "options": options_value,
                    "correct_answer": q.get("correct_answer", ""),
                    "explanation": q.get("explanation", ""),
                    "type": q.get("type", "single_choice"),
                    "tags": tags_value,
                    "source": q.get("source", "imported"),
                    "batch_id": q.get("batch_id"),
                },
            )
            imported += 1
        except Exception:
            failed += 1
            errors.append({"index": idx, "reason": "题目数据无效或写入失败"})

    return {
        "success": True,
        "imported": imported,
        "failed": failed,
        "total": len(questions),
        "errors": errors[:10],
    }
