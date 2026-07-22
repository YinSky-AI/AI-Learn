import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.knowledge_graph import get_knowledge_graph


class _Session:
    def __init__(self, user):
        self.user = user

    async def get(self, model, user_id):
        return self.user if user_id == self.user.id else None


@pytest.mark.asyncio
async def test_api_returns_authenticated_users_enriched_graph():
    user = SimpleNamespace(
        id=uuid.uuid4(),
        behavior_profile={
            "knowledge_mastery": {"拼音": {"level": 0.75, "total": 2, "correct": 1}},
            "subject_mastery": {},
            "study_stats": {"total_time_minutes": 0, "daily_records": {}},
            "processed_answer_ids": [],
        },
    )

    response = await get_knowledge_graph(subject="语文", user_id=user.id, db=_Session(user))

    assert response["code"] == "SUCCESS"
    assert response["data"]["subject"] == "chinese"
    assert response["data"]["learned_leaf_count"] == 1


@pytest.mark.asyncio
async def test_api_rejects_unsupported_subject_with_plain_chinese_message():
    user = SimpleNamespace(id=uuid.uuid4(), behavior_profile=None)

    with pytest.raises(HTTPException) as exc:
        await get_knowledge_graph(subject="物理", user_id=user.id, db=_Session(user))

    assert exc.value.status_code == 404
    assert exc.value.detail == {"code": "GRAPH_001", "message": "暂不支持该学科的知识图谱"}
