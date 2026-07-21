"""课程相关测试"""
import pytest


@pytest.mark.asyncio
async def test_list_courses(client):
    response = await client.get("/api/v1/courses?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "SUCCESS"
    assert "items" in data["data"]


@pytest.mark.asyncio
async def test_course_detail_not_found(client):
    response = await client.get("/api/v1/courses/not-a-real-course")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "BIZ_001"
    assert data["data"] is None
    assert data["message"] == "课程不存在"
