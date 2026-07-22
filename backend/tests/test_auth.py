"""认证相关测试"""
import pytest


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
