import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.knowledge_graph import get_knowledge_graph


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return _Scalars(self.values)


class _Session:
    def __init__(self, results):
        self.results = iter(results)

    async def execute(self, _statement):
        return _Result(next(self.results))


@pytest.mark.asyncio
async def test_api_returns_authenticated_users_enriched_graph():
    user_id = uuid.uuid4()
    node_id = uuid.uuid4()
    node = SimpleNamespace(
        id=node_id,
        code="legacy-pinyin",
        title="拼音",
        description="拼音",
        difficulty_level="DIFF_EASY",
        prerequisites=[],
    )
    state = SimpleNamespace(knowledge_node_id=node_id, p_known=0.75)

    response = await get_knowledge_graph(
        subject="语文", user_id=user_id, db=_Session([[node], [state]])
    )

    assert response["code"] == "SUCCESS"
    assert response["data"]["subject"] == "chinese"
    assert response["data"]["learned_leaf_count"] == 1


@pytest.mark.asyncio
async def test_api_rejects_unsupported_subject_with_plain_chinese_message():
    with pytest.raises(HTTPException) as exc:
        await get_knowledge_graph(
            subject="物理", user_id=uuid.uuid4(), db=_Session([])
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == {"code": "GRAPH_001", "message": "暂不支持该学科的知识图谱"}
