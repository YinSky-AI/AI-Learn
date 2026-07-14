# -*- coding: utf-8 -*-
"""
管理后台路由
使用 Jinja2 模板渲染 HTML 页面，独立 session 验证
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from jinja2 import Environment, FileSystemLoader

router = APIRouter(prefix="/admin", tags=["管理后台"])

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

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
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ============ Session 验证 ============

def _check_session(request: Request):
    """HTML 页面会话检查，未登录返回重定向"""
    if request.cookies.get("admin_session") != "authenticated":
        return RedirectResponse(url="/admin/login", status_code=302)
    return None


def _check_api_auth(request: Request):
    """API 端点会话验证，未登录返回 401 JSON"""
    if request.cookies.get("admin_session") != "authenticated":
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "未登录或会话已过期"},
        )
    return None


# ============ 登录 / 登出 ============

@router.get("/login", response_class=HTMLResponse)
async def login_page(error: str = ""):
    """登录页面"""
    template = jinja_env.get_template("login.html")
    return HTMLResponse(template.render(error=error))


@router.post("/login")
async def login_submit(password: str = Form(...)):
    """登录提交"""
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin", status_code=302)
        response.set_cookie("admin_session", "authenticated", max_age=86400, httponly=True)
        return response
    template = jinja_env.get_template("login.html")
    return HTMLResponse(template.render(error="密码错误，请重试"))


@router.get("/logout")
async def logout():
    """退出登录"""
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_session")
    return response


# ============ 仪表盘 ============

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """仪表盘"""
    redirect = _check_session(request)
    if redirect:
        return redirect

    # 总用户数
    total_users = (await db.execute(
        text("SELECT COUNT(*) FROM public.users WHERE deleted_at IS NULL")
    )).scalar()

    # 总课程数
    total_courses = (await db.execute(
        text("SELECT COUNT(*) FROM public.courses")
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
        "FROM public.courses ORDER BY enroll_count DESC NULLS LAST LIMIT 10"
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
        "FROM public.courses GROUP BY subject ORDER BY cnt DESC"
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
    """课程管理页面"""
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
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
):
    """课程列表 API"""
    auth = _check_api_auth(request)
    if auth:
        return auth

    conditions = []
    params: dict = {}

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

    # 总数
    total = (await db.execute(
        text(f"SELECT COUNT(*) FROM public.courses WHERE {where}"), params
    )).scalar()

    # 数据
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
    """获取单个课程信息（课时管理页用）"""
    auth = _check_api_auth(request)
    if auth:
        return auth
    try:
        result = await db.execute(
            text("SELECT id, title, subject, difficulty, age_group, total_lessons, is_active FROM courses WHERE id = :id"),
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
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


@router.put("/courses/api/{course_id}/status")
async def course_status_api(
    course_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """修改课程启用/停用状态"""
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
        text("UPDATE public.courses SET is_active = :is_active, updated_at = NOW() WHERE id = :id"),
        {"is_active": new_status, "id": course_id},
    )

    return {"success": True, "message": "状态已更新"}


@router.delete("/courses/api/{course_id}")
async def course_delete_api(
    course_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """删除课程（同时清理关联数据）"""
    auth = _check_api_auth(request)
    if auth:
        return auth

    # 按依赖顺序清理关联数据
    await db.execute(
        text("DELETE FROM public.user_lessons WHERE course_id = :id"),
        {"id": course_id},
    )
    await db.execute(
        text("DELETE FROM public.user_courses WHERE course_id = :id"),
        {"id": course_id},
    )
    await db.execute(
        text("DELETE FROM public.lessons WHERE course_id = :id"),
        {"id": course_id},
    )
    result = await db.execute(
        text("DELETE FROM public.courses WHERE id = :id"),
        {"id": course_id},
    )

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "课程不存在"})

    return {"success": True, "message": "课程已删除"}


# ============ 课时管理页面 ============

@router.get("/lessons", response_class=HTMLResponse)
async def lessons_page(request: Request, course_id: Optional[str] = Query(None)):
    """课时管理页面"""
    redirect = _check_session(request)
    if redirect:
        return redirect
    template = jinja_env.get_template("lessons.html")
    return HTMLResponse(template.render(active_page="lessons", course_id=course_id))


# ============ 用户管理页面 ============

@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: AsyncSession = Depends(get_db)):
    """用户管理页面"""
    redirect = _check_session(request)
    if redirect:
        return redirect
    template = jinja_env.get_template("users.html")
    return HTMLResponse(template.render(active_page="users"))


# ============ 用户 API ============

@router.get("/users/api/list")
async def users_api_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    keyword: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
):
    """用户列表 API"""
    auth = _check_api_auth(request)
    if auth:
        return auth

    conditions = ["deleted_at IS NULL"]
    params: dict = {}

    if keyword:
        conditions.append("(nickname ILIKE :kw OR email ILIKE :kw)")
        params["kw"] = f"%{keyword}%"
    if age_group:
        conditions.append("age_group = :ag")
        params["ag"] = age_group

    where = " AND ".join(conditions)

    # 总数
    total = (await db.execute(
        text(f"SELECT COUNT(*) FROM public.users WHERE {where}"), params
    )).scalar()

    # 数据
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
    """修改用户信息（昵称、年龄段）"""
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

    updates = []
    params: dict = {"id": user_id}

    if nickname is not None:
        updates.append("nickname = :nickname")
        params["nickname"] = nickname
    if age_group is not None:
        updates.append("age_group = :age_group")
        params["age_group"] = age_group if age_group else None

    updates.append("updated_at = NOW()")

    sql = f"UPDATE public.users SET {', '.join(updates)} WHERE id = :id"
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
    """删除用户（同时清理关联数据）"""
    auth = _check_api_auth(request)
    if auth:
        return auth

    # 按依赖顺序清理关联数据
    await db.execute(
        text("DELETE FROM public.user_lessons WHERE user_id = :id"),
        {"id": user_id},
    )
    await db.execute(
        text("DELETE FROM public.user_courses WHERE user_id = :id"),
        {"id": user_id},
    )
    result = await db.execute(
        text("DELETE FROM public.users WHERE id = :id"),
        {"id": user_id},
    )

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "用户不存在"})

    return {"success": True, "message": "用户已删除"}


# ============ 课程创建 API ============

@router.post("/courses/api/create")
async def course_create_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """创建课程"""
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
                "slug": body.get("slug"),
            },
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"创建失败: {str(e)}"})

    return {"success": True, "message": "课程已创建", "id": course_id}


# ============ 课程编辑 API ============

@router.put("/courses/api/{course_id}")
async def course_update_api(
    course_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """编辑课程（动态更新提供的字段）"""
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

    for field in allowed_fields:
        if field in body:
            updates.append(f"{field} = :{field}")
            params[field] = body[field]

    # tags 需要特殊处理（字符串 -> JSON）
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

    sql = f"UPDATE public.courses SET {', '.join(updates)} WHERE id = :id"
    result = await db.execute(text(sql), params)

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "课程不存在"})

    return {"success": True, "message": "课程已更新"}


# ============ 课时列表 API ============

@router.get("/lessons/api/list")
async def lessons_api_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    course_id: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """课时列表 API"""
    auth = _check_api_auth(request)
    if auth:
        return auth

    # 总数
    total = (await db.execute(
        text("SELECT COUNT(*) FROM public.lessons WHERE course_id = :course_id"),
        {"course_id": course_id},
    )).scalar()

    # 分页数据
    offset = (page - 1) * page_size
    rows = (await db.execute(
        text(
            'SELECT id, course_id, title, description, type, duration, "order", '
            "content, is_active, created_at "
            "FROM public.lessons WHERE course_id = :course_id "
            'ORDER BY "order" LIMIT :limit OFFSET :offset'
        ),
        {"course_id": course_id, "limit": page_size, "offset": offset},
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
    """创建课时"""
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

        # 更新课程的 total_lessons
        await db.execute(
            text(
                "UPDATE public.courses SET total_lessons = ("
                "SELECT COUNT(*) FROM public.lessons WHERE course_id = :id AND is_active = true"
                "), updated_at = NOW() WHERE id = :id"
            ),
            {"id": course_id},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"创建失败: {str(e)}"})

    return {"success": True, "message": "课时已创建", "id": lesson_id}


# ============ 课时编辑 API ============

@router.put("/lessons/api/{lesson_id}")
async def lesson_update_api(
    lesson_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """编辑课时（动态更新提供的字段）"""
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

    for field in allowed_fields:
        if field in body:
            # "order" 是 PostgreSQL 保留字，需要双引号包裹
            col = f'"{field}"' if field == "order" else field
            updates.append(f"{col} = :{field}")
            params[field] = body[field]

    if not updates:
        return JSONResponse(status_code=400, content={"success": False, "message": "没有需要更新的字段"})

    updates.append("updated_at = NOW()")

    sql = f"UPDATE public.lessons SET {', '.join(updates)} WHERE id = :id"
    result = await db.execute(text(sql), params)

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "课时不存在"})

    # 如果修改了 order 或 is_active，重新计算课程的 total_lessons
    if "order" in body or "is_active" in body:
        course_row = (await db.execute(
            text("SELECT course_id FROM public.lessons WHERE id = :id"),
            {"id": lesson_id},
        )).fetchone()

        if course_row and course_row[0]:
            await db.execute(
                text(
                    "UPDATE public.courses SET total_lessons = ("
                    "SELECT COUNT(*) FROM public.lessons WHERE course_id = :cid AND is_active = true"
                    "), updated_at = NOW() WHERE id = :cid"
                ),
                {"cid": str(course_row[0])},
            )

    return {"success": True, "message": "课时已更新"}


# ============ 课时删除 API ============

@router.delete("/lessons/api/{lesson_id}")
async def lesson_delete_api(
    lesson_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """删除课时（同时清理关联数据）"""
    auth = _check_api_auth(request)
    if auth:
        return auth

    # 先获取 lesson 的 course_id
    lesson_row = (await db.execute(
        text("SELECT course_id FROM public.lessons WHERE id = :id"),
        {"id": lesson_id},
    )).fetchone()

    if not lesson_row:
        return JSONResponse(status_code=404, content={"success": False, "message": "课时不存在"})

    course_id = str(lesson_row[0])

    # 按依赖顺序清理关联数据
    await db.execute(
        text("DELETE FROM public.user_lessons WHERE lesson_id = :id"),
        {"id": lesson_id},
    )
    await db.execute(
        text("DELETE FROM public.chat_messages WHERE lesson_id = :id"),
        {"id": lesson_id},
    )
    result = await db.execute(
        text("DELETE FROM public.lessons WHERE id = :id"),
        {"id": lesson_id},
    )

    if result.rowcount == 0:
        return JSONResponse(status_code=404, content={"success": False, "message": "课时不存在"})

    # 重新计算课程的 total_lessons
    await db.execute(
        text(
            "UPDATE public.courses SET total_lessons = ("
            "SELECT COUNT(*) FROM public.lessons WHERE course_id = :cid AND is_active = true"
            "), updated_at = NOW() WHERE id = :cid"
        ),
        {"cid": course_id},
    )

    return {"success": True, "message": "课时已删除"}


# ============ 课时详情 API ============

@router.get("/lessons/api/{lesson_id}")
async def lesson_detail_api(
    lesson_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """课时详情 API"""
    auth = _check_api_auth(request)
    if auth:
        return auth

    row = (await db.execute(
        text(
            'SELECT id, course_id, title, description, type, duration, "order", '
            "content, is_active, created_at, updated_at "
            "FROM public.lessons WHERE id = :id"
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
    """课时批量排序"""
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
                text('UPDATE public.lessons SET "order" = :order, updated_at = NOW() WHERE id = :id'),
                {"id": item_id, "order": item_order},
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"排序失败: {str(e)}"})

    return {"success": True, "message": "排序已更新"}