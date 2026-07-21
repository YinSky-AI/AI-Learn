import uuid
from types import SimpleNamespace

import pytest


def _question(index: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        difficulty_level="DIFF_EASY",
        question_type="CHOICE",
        question_body=f"专项题目 {index}",
        options=[{"key": "A", "value": "选项 A"}],
        correct_answer="A",
        explanation="不应随题目下发",
        standard_time_seconds=30,
    )


@pytest.mark.asyncio
async def test_practice_endpoint_returns_answer_safe_questions_limited_to_ten(monkeypatch):
    from app.api.v1 import knowledge_graph as graph_api

    actual_node_id = uuid.uuid4()

    async def fake_get_practice_set(*_args, **_kwargs):
        return SimpleNamespace(id=actual_node_id, difficulty_level="DIFF_EASY"), [
            _question(index) for index in range(12)
        ]

    monkeypatch.setattr(
        graph_api.KnowledgeGraphService,
        "get_practice_set",
        fake_get_practice_set,
    )

    response = await graph_api.get_knowledge_graph_practice(
        graph_node_id="math-fraction-operations",
        subject="math",
        name="分数运算",
        _user_id=uuid.uuid4(),
        db=object(),
    )

    assert response.data.knowledge_node_id == actual_node_id
    assert response.data.graph_node_id == "math-fraction-operations"
    assert response.data.name == "分数运算"
    assert len(response.data.questions) == 10
    assert all(not hasattr(question, "correct_answer") for question in response.data.questions)
    assert all(not hasattr(question, "explanation") for question in response.data.questions)


def test_practice_rejects_a_leaf_name_from_another_graph_node():
    from app.services.knowledge_graph_service import KnowledgeGraphService

    with pytest.raises(ValueError, match="知识点信息不匹配"):
        KnowledgeGraphService.resolve_leaf(
            "math",
            "math-fraction-operations",
            "整数运算",
        )
