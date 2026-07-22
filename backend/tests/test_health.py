"""健康检查测试"""
import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code in {200, 503}
    data = response.json()
    assert data["code"] in {"SUCCESS", "SERVICE_UNAVAILABLE"}
    assert data["data"]["status"] in {"healthy", "unready"}


@pytest.mark.asyncio
async def test_liveness_and_readiness_contracts(client):
    live = await client.get("/live")
    assert live.status_code == 200
    assert live.json()["data"]["status"] == "alive"
    ready = await client.get("/ready")
    assert ready.status_code in {200, 503}
    assert set(ready.json()["data"]["checks"]) == {"database", "redis"}
