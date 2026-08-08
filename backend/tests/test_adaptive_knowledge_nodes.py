import uuid

import pytest

from app.domain.equation_taxonomy import KnowledgePointCode
from app.services.seed_bank import (
    EQUATION_KNOWLEDGE_NODE_SEEDS,
    upsert_equation_knowledge_nodes,
)


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)


class FakeResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return FakeScalarResult(self.values)


class FakeSession:
    def __init__(self):
        self.nodes = []
        self.added = []

    async def execute(self, _statement):
        return FakeResult(self.nodes)

    def add(self, node):
        self.nodes.append(node)
        self.added.append(node)

    async def flush(self):
        for node in self.nodes:
            if node.id is None:
                node.id = uuid.uuid5(uuid.NAMESPACE_URL, f"test:{node.code}")


def test_equation_seed_catalog_has_all_six_canonical_codes_without_uuid_literals():
    """Omitting a skill or hard-coding environment IDs must make this test fail."""

    assert {seed.code for seed in EQUATION_KNOWLEDGE_NODE_SEEDS} == set(
        KnowledgePointCode
    )
    assert all(seed.prerequisite_codes for seed in EQUATION_KNOWLEDGE_NODE_SEEDS if seed.code is KnowledgePointCode.EQUATION_WORD_MODELING)
    assert all(not hasattr(seed, "id") for seed in EQUATION_KNOWLEDGE_NODE_SEEDS)


@pytest.mark.asyncio
async def test_equation_node_upsert_resolves_prerequisites_to_persisted_ids():
    """Saving prerequisite codes or environment-specific UUIDs must make this fail."""

    session = FakeSession()

    nodes = await upsert_equation_knowledge_nodes(
        session,
        subject_code="SUBJ_MATH",
        age_group_code="AGE_13_15",
    )

    by_code = {node.code: node for node in nodes}
    move_terms = by_code[KnowledgePointCode.MOVE_TERMS_SIGN]
    word_modeling = by_code[KnowledgePointCode.EQUATION_WORD_MODELING]
    assert move_terms.prerequisites == [
        by_code[KnowledgePointCode.EQUATION_EQUIVALENCE].id
    ]
    assert set(word_modeling.prerequisites) == {
        by_code[code].id
        for code in (
            KnowledgePointCode.DISTRIBUTIVE_EXPANSION,
            KnowledgePointCode.COMBINE_LIKE_TERMS,
            KnowledgePointCode.MOVE_TERMS_SIGN,
            KnowledgePointCode.NORMALIZE_COEFFICIENT,
        )
    }

    await upsert_equation_knowledge_nodes(
        session,
        subject_code="SUBJ_MATH",
        age_group_code="AGE_13_15",
    )
    assert len(session.nodes) == 6
    assert len(session.added) == 6
