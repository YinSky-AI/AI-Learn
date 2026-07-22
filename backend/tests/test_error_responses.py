"""错误响应格式回归测试。"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app


@app.get("/test-error-dict-details", include_in_schema=False)
async def raise_error_dict_details():
    raise HTTPException(
        status_code=500,
        detail={
            "code": "INTERNAL_DETAIL",
            "message": "服务暂时不可用",
            "traceback": "不应暴露的内部详情",
        },
    )


@app.get("/test-validation-error", include_in_schema=False)
async def raise_validation_error(quantity: int):
    return {"quantity": quantity}


@app.get("/test-unhandled-error", include_in_schema=False)
async def raise_unhandled_error():
    raise RuntimeError("traceback: 不应暴露的内部详情")


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_dict_exception_returns_message_only(client):
    response = await client.get("/test-error-dict-details")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "HTTP_500"
    assert body["message"] == "服务暂时不可用"
    assert set(body) == {"code", "message", "data", "meta"}
    assert "INTERNAL_DETAIL" not in response.text
    assert "不应暴露的内部详情" not in response.text
    assert "traceback" not in response.text.lower()


@pytest.mark.asyncio
async def test_validation_error_hides_pydantic_details(client):
    response = await client.get("/test-validation-error?quantity=invalid")

    assert response.status_code == 422
    body = response.json()
    assert body == {
        "code": "VALIDATION_ERROR",
        "message": "请求参数验证失败",
        "data": None,
        "meta": None,
    }
    assert "invalid" not in response.text
    assert "pydantic" not in response.text.lower()


@pytest.mark.asyncio
async def test_unhandled_exception_hides_internal_detail(client):
    response = await client.get("/test-unhandled-error")

    assert response.status_code == 500
    body = response.json()
    assert body == {
        "code": "INTERNAL_ERROR",
        "message": "服务暂时不可用，请稍后重试",
        "data": None,
        "meta": None,
    }
    assert "不应暴露的内部详情" not in response.text
    assert "traceback" not in response.text.lower()
