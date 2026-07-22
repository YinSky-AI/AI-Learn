"""认证相关测试"""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_register_and_login(client):
    # 注册
    register_data = {
        "username": "test_user",
        "nickname": "测试用户",
        "email": "test@example.com",
        "password": "123456",
        "password_confirm": "123456",
        "age": 12,
        "gender": "male",
    }
    response = await client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 200

    # 登录
    login_data = {"username": "test@example.com", "password": "123456"}
    response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "SUCCESS"
    assert "access_token" in data["data"]


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    login_data = {"username": "wrong@example.com", "password": "wrongpass"}
    response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "HTTP_401"
    assert data["message"] == "用户名或密码错误"


@pytest.mark.asyncio
async def test_credential_version_revokes_access_and_refresh_tokens(client, db_session):
    response = await client.post("/api/v1/auth/register", json={
        "username": "principal_user", "nickname": "主体用户", "email": "principal@example.com",
        "password": "123456", "age": 12,
    })
    tokens = response.json()["data"]

    await db_session.execute(
        text("UPDATE users SET credential_version = credential_version + 1, credentials_revoked_at = NOW() WHERE email=:email"),
        {"email": "principal@example.com"},
    )
    await db_session.commit()

    denied = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert denied.status_code == 401
    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_is_single_use_after_rotation(client):
    response = await client.post("/api/v1/auth/register", json={
        "username": "rotate_user", "nickname": "轮换用户", "email": "rotate@example.com",
        "password": "123456", "age": 12,
    })
    refresh_token = response.json()["data"]["refresh_token"]
    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert rotated.status_code == 200
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401
