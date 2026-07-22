"""管理后台身份、会话与 CSRF 边界回归测试。"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from loguru import logger
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import hash_password
from app.main import app
from app.models.user import User
from app.services.admin_auth import AdminAuthService


class MemoryRedis:
    """只替换 Redis 传输层，保留真实签名和会话逻辑。"""

    def __init__(self):
        self.values: dict[str, str] = {}

    @property
    def client(self):
        return self

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, *, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def delete(self, key: str):
        return int(self.values.pop(key, None) is not None)


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 7, 22, 8, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def _login_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


@pytest_asyncio.fixture
async def admin_access(client, db_session, db_engine):
    password = "Only-For-P0-02-Test!"
    admin = User(
        nickname="安全管理员",
        email="admin-p002@example.test",
        password_hash=hash_password(password),
        birth_date=date(1990, 1, 1),
        age_group="adult",
        is_admin=True,
    )
    member = User(
        nickname="普通用户",
        email="member-p002@example.test",
        password_hash=hash_password(password),
        birth_date=date(2012, 1, 1),
        age_group="AGE_10_12",
        is_admin=False,
    )
    db_session.add_all([admin, member])
    await db_session.commit()

    clock = MutableClock()
    test_session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    service = AdminAuthService(
        session_factory=test_session_factory,
        redis=MemoryRedis(),
        clock=clock,
        session_ttl_seconds=300,
        cookie_secure=False,
    )
    previous = app.state.admin_auth_service
    app.state.admin_auth_service = service
    try:
        yield {
            "client": client,
            "admin": admin,
            "member": member,
            "password": password,
            "clock": clock,
            "service": service,
            "db": db_session,
        }
    finally:
        app.state.admin_auth_service = previous


async def _login(access, *, identifier: str | None = None, password: str | None = None):
    client = access["client"]
    page = await client.get("/admin/login")
    csrf_token = _login_csrf(page.text)
    return await client.post(
        "/admin/login",
        data={
            "identifier": identifier or access["admin"].email,
            "password": password or access["password"],
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )


@pytest.mark.asyncio
async def test_legacy_static_cookie_cannot_authorize_admin_write(client):
    client.cookies.set("admin_session", "authenticated")
    response = await client.put(
        f"/admin/courses/api/{uuid.uuid4()}/status",
        json={"status": "published"},
    )

    assert response.status_code == 401
    assert response.text == "未登录或会话已过期"


@pytest.mark.asyncio
async def test_only_active_admin_identity_can_login(admin_access):
    access = admin_access
    audit_messages: list[str] = []
    sink_id = logger.add(
        lambda message: audit_messages.append(str(message)),
        format="{message}",
    )
    try:
        denied = await _login(access, identifier=access["member"].email)
        access["service"].cookie_secure = True
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://test",
        ) as secure_client:
            secure_access = {**access, "client": secure_client}
            accepted = await _login(secure_access)
    finally:
        logger.remove(sink_id)

    assert denied.status_code == 401
    assert "账号或密码错误" in denied.text
    assert "admin_session" not in denied.cookies
    session_cookie = accepted.headers.get_list("set-cookie")

    assert accepted.status_code == 302
    assert accepted.headers["location"] == "/admin"
    assert any(
        "admin_session=" in value
        and "HttpOnly" in value
        and "Secure" in value
        and "SameSite=strict" in value
        and "Max-Age=300" in value
        for value in session_cookie
    )
    audit_text = "\n".join(audit_messages)
    assert "event=admin_login_rejected" in audit_text
    assert "event=admin_login_succeeded" in audit_text
    assert access["password"] not in audit_text
    assert access["admin"].email not in audit_text


@pytest.mark.asyncio
async def test_signed_session_rejects_tamper_expiry_and_role_revocation(admin_access):
    access = admin_access
    response = await _login(access)
    token = response.cookies["admin_session"]

    access["client"].cookies.set("admin_session", token[:-1] + ("A" if token[-1] != "A" else "B"))
    tampered = await access["client"].get("/admin/courses", follow_redirects=False)
    assert tampered.status_code == 302
    assert tampered.headers["location"] == "/admin/login"

    access["client"].cookies.set("admin_session", token)
    access["clock"].advance(301)
    expired = await access["client"].get("/admin/courses", follow_redirects=False)
    assert expired.status_code == 302

    access["clock"].value -= timedelta(seconds=301)
    access["admin"].is_admin = False
    await access["db"].commit()
    demoted = await access["client"].get("/admin/courses", follow_redirects=False)
    assert demoted.status_code == 302


@pytest.mark.asyncio
async def test_logout_revokes_session_and_prevents_cookie_reuse(admin_access):
    access = admin_access
    response = await _login(access)
    token = response.cookies["admin_session"]
    csrf_token = response.cookies["admin_csrf"]

    logged_out = await access["client"].post(
        "/admin/logout",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert logged_out.status_code == 302

    access["client"].cookies.set("admin_session", token)
    replay = await access["client"].get("/admin/courses", follow_redirects=False)
    assert replay.status_code == 302
    assert replay.headers["location"] == "/admin/login"


@pytest.mark.asyncio
async def test_all_admin_write_methods_require_session_bound_csrf(admin_access):
    access = admin_access
    response = await _login(access)
    assert response.status_code == 302

    unsafe_routes = {
        (method, route.path)
        for route in app.routes
        if route.path.startswith("/admin/")
        for method in (route.methods or set())
        if method in {"POST", "PUT", "PATCH", "DELETE"}
        and route.path not in {"/admin/login", "/admin/logout"}
    }
    assert {method for method, _ in unsafe_routes} == {"POST", "PUT", "DELETE"}

    for method, path in sorted(unsafe_routes):
        concrete_path = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
        denied = await access["client"].request(method, concrete_path)
        assert denied.status_code == 403, (method, path, denied.text)
        assert denied.text == "安全校验失败，请刷新页面后重试"

    generic_patch = await access["client"].patch("/admin/future-write")
    assert generic_patch.status_code == 403

    wrong = await access["client"].put(
        f"/admin/users/api/{access['admin'].id}",
        headers={"X-CSRF-Token": "wrong"},
        json={"nickname": "不应写入"},
    )
    assert wrong.status_code == 403


@pytest.mark.asyncio
async def test_valid_csrf_allows_authorized_change(admin_access):
    access = admin_access
    login = await _login(access)
    csrf_token = login.cookies["admin_csrf"]

    changed = await access["client"].put(
        f"/admin/users/api/{access['admin'].id}",
        headers={"X-CSRF-Token": csrf_token},
        json={"nickname": "已审计管理员"},
    )

    assert changed.status_code == 200
    assert changed.json() == {"success": True, "message": "用户已更新"}


@pytest.mark.asyncio
async def test_login_requires_matching_csrf_cookie(admin_access):
    page = await admin_access["client"].get("/admin/login")
    csrf_token = _login_csrf(page.text)
    denied = await admin_access["client"].post(
        "/admin/login",
        data={
            "identifier": admin_access["admin"].email,
            "password": admin_access["password"],
            "csrf_token": csrf_token + "tampered",
        },
    )

    assert denied.status_code == 403
    assert denied.text == "安全校验失败，请刷新页面后重试"


def test_admin_source_has_no_default_password_or_static_cookie_boundary():
    source = (
        Path(__file__).resolve().parents[1] / "app" / "admin" / "routes.py"
    ).read_text(encoding="utf-8")

    assert "admin123" not in source
    assert '== "authenticated"' not in source
