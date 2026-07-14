"""课程相关测试"""
import pytest


@pytest.mark.asyncio
async def test_list_courses(client):
    response = await client.get("/api/v1/courses?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "000000"
    assert "items" in data["data"]


@pytest.mark.asyncio
async def test_get_course_detail(client):
    response = await client.get("/api/v1/courses/course-1")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "000000"
    assert data["data"]["title"] == "趣味数学入门"
