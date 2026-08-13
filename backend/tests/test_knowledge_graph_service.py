import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.models.adaptive_learning import KnowledgeMasteryState
from app.models.content import AgeGroup, KnowledgeNode, Subject
from app.models.user import User

from app.services.knowledge_graph_service import (
    KnowledgeGraphService,
    KnowledgeNodeFact,
    UnknownSubjectError,
)


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
        [
            KnowledgeNodeFact(
                uuid.uuid4(), "legacy-fraction", "异分母分数加法", "分数说明", "DIFF_MEDIUM", (), 0.8
            ),
            KnowledgeNodeFact(
                uuid.uuid4(), "legacy-decimal", "小数运算", "小数说明", "DIFF_EASY", (), 0.4
            ),
        ],
    )

    fraction = _find(graph, "math-fraction-operations")
    decimal = _find(graph, "math-decimal-operations")
    number_operations = _find(graph, "math-number-operations")

    assert graph["subject"] == "math"
    assert fraction["mastery"] == pytest.approx(0.8)
    assert fraction["mastery_percent"] == 80
    assert decimal["mastery"] == pytest.approx(0.4)
    assert fraction["difficulty_level"] == "DIFF_MEDIUM"
    assert fraction["description"] == "分数说明"
    assert number_operations["mastery"] == pytest.approx(0.6)
    assert number_operations["mastery_percent"] == 60
    assert fraction["practice_href"].startswith("/learning?")
    assert "knowledge_point=" in fraction["practice_href"]


@pytest.mark.asyncio
async def test_graph_reads_database_mastery_and_ignores_legacy_behavior_json():
    user_id = uuid.uuid4()
    node_id = uuid.uuid4()
    node = SimpleNamespace(
        id=node_id,
        code="legacy-pinyin",
        title="拼音",
        description="数据库说明",
        difficulty_level="DIFF_EASY",
        prerequisites=[],
    )
    state = SimpleNamespace(knowledge_node_id=node_id, p_known=0.72)

    graph = await KnowledgeGraphService(_Session([[node], [state]])).get_for_user(
        user_id, "chinese"
    )

    assert _find(graph, "chinese-pinyin")["mastery_percent"] == 72
    assert graph["learned_leaf_count"] == 1
    assert _find(graph, "chinese-pinyin")["description"] == "数据库说明"


@pytest.mark.asyncio
async def test_graph_loads_canonical_node_and_bkt_state_from_database(db_session):
    user_id = uuid.uuid4()
    node_id = uuid.uuid4()
    db_session.add_all(
        [
            Subject(code="SUBJ_MATH", name="数学", sort_order=0),
            AgeGroup(
                code="AGE_KG", name="图谱", min_age=12, max_age=15, theme_config={}
            ),
            User(
                id=user_id,
                nickname="图谱学生",
                email=f"graph-{user_id}@example.test",
                password_hash="hash",
                birth_date=date(2012, 1, 1),
                age_group="AGE_KG",
                behavior_profile={
                    "knowledge_mastery": {
                        "方程": {"level": 0.99, "total": 100, "correct": 99}
                    }
                },
            ),
            KnowledgeNode(
                id=node_id,
                code="equation_equivalence",
                title="等式与等价变形",
                description="数据库中的等价变形说明",
                subject_code="SUBJ_MATH",
                age_group_code="AGE_KG",
                difficulty_level="DIFF_EASY",
                content_type="TYPE_QUIZ",
                content_body="测试",
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        KnowledgeMasteryState(
            user_id=user_id,
            knowledge_node_id=node_id,
            p_known=0.42,
            model_version="bkt-equation-v1",
            observation_count=1,
        )
    )
    await db_session.flush()

    graph = await KnowledgeGraphService(db_session).get_for_user(user_id, "math")
    equation = _find(graph, "math-equations")

    assert equation["name"] == "等式与等价变形"
    assert equation["mastery"] == pytest.approx(0.42)
    assert equation["mastery"] != pytest.approx(0.99)
    assert equation["knowledge_node_id"] == node_id


def test_unknown_subject_is_rejected_with_user_facing_message():
    with pytest.raises(UnknownSubjectError, match="暂不支持该学科"):
        KnowledgeGraphService.enrich_graph("physics", {})


def test_static_leaf_accepts_the_canonical_database_title_alias():
    subject, leaf = KnowledgeGraphService.resolve_leaf(
        "math", "math-equations", "等式与等价变形"
    )

    assert subject == "math"
    assert leaf["knowledge_code"] == "equation_equivalence"


def test_all_mvp_subjects_have_two_to_three_level_trees():
    for subject in ("math", "chinese", "english"):
        graph = KnowledgeGraphService.enrich_graph(subject, [])
        assert graph["children"]
        assert all(group["children"] for group in graph["children"])
        assert all(child["is_leaf"] for group in graph["children"] for child in group["children"])
        assert all(child["mastery"] is None for group in graph["children"] for child in group["children"])
