"""错误响应格式回归测试。"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_dict_exception_returns_message_only(client):
    response = await client.get("/test-error-dict")

    assert response.status_code == 500
    body = response.json()
    assert body["message"] == "服务暂时不可用"
    assert set(body) == {"code", "message", "data", "meta"}
    assert "traceback" not in response.text.lower()
