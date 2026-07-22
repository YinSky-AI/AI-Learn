import uuid
from types import SimpleNamespace

import pytest

from app.services.knowledge_graph_service import KnowledgeGraphService, UnknownSubjectError


class _Session:
    def __init__(self, user):
        self.user = user

    async def get(self, model, user_id):
        return self.user if user_id == self.user.id else None


def _find(node: dict, node_id: str) -> dict:
    if node.get("id") == node_id:
        return node
    for child in node.get("children", []):
        found = _find(child, node_id)
        if found:
            return found
    return {}


def test_graph_enriches_leaves_and_rolls_up_only_learned_children():
    graph = KnowledgeGraphService.enrich_graph(
        "math",
        {"异分母分数加法": 0.8, "小数运算": 0.4},
    )

    fraction = _find(graph, "math-fraction-operations")
    decimal = _find(graph, "math-decimal-operations")
    number_operations = _find(graph, "math-number-operations")

    assert graph["subject"] == "math"
    assert fraction["mastery"] == pytest.approx(0.8)
    assert fraction["mastery_percent"] == 80
    assert decimal["mastery"] == pytest.approx(0.4)
    assert number_operations["mastery"] == pytest.approx(0.6)
    assert number_operations["mastery_percent"] == 60
    assert fraction["practice_href"].startswith("/learning?")
    assert "knowledge_point=" in fraction["practice_href"]


@pytest.mark.asyncio
async def test_graph_reads_current_users_behavior_heatmap():
    user = SimpleNamespace(
        id=uuid.uuid4(),
        behavior_profile={
            "knowledge_mastery": {
                "拼音": {"level": 0.72, "total": 4, "correct": 3},
            },
            "subject_mastery": {},
            "study_stats": {"total_time_minutes": 0, "daily_records": {}},
            "processed_answer_ids": [],
        },
    )

    graph = await KnowledgeGraphService(_Session(user)).get_for_user(user.id, "chinese")

    assert _find(graph, "chinese-pinyin")["mastery_percent"] == 72
    assert graph["learned_leaf_count"] == 1


def test_unknown_subject_is_rejected_with_user_facing_message():
    with pytest.raises(UnknownSubjectError, match="暂不支持该学科"):
        KnowledgeGraphService.enrich_graph("physics", {})


def test_all_mvp_subjects_have_two_to_three_level_trees():
    for subject in ("math", "chinese", "english"):
        graph = KnowledgeGraphService.enrich_graph(subject, {})
        assert graph["children"]
        assert all(group["children"] for group in graph["children"])
        assert all(child["is_leaf"] for group in graph["children"] for child in group["children"])
        assert all(child["mastery"] is None for group in graph["children"] for child in group["children"])
