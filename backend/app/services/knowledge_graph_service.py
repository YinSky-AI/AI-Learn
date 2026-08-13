"""以数据库知识节点和 BKT 状态生成当前用户的知识图谱。"""

from __future__ import annotations

import copy
import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.knowledge_graph import KNOWLEDGE_GRAPHS, SUBJECT_ALIASES
from app.models.content import KnowledgeNode, Question
from app.models.adaptive_learning import KnowledgeMasteryState
from app.domain.bkt import BKT_EQUATION_V1
from app.services.content_service import is_question_practice_ready


class UnknownSubjectError(ValueError):
    """请求的学科尚未进入知识图谱 MVP。"""


@dataclass(frozen=True, slots=True)
class KnowledgeNodeFact:
    id: uuid.UUID
    code: str
    title: str
    description: str | None
    difficulty_level: str
    prerequisites: tuple[uuid.UUID, ...]
    p_known: float | None


class KnowledgeGraphService:
    """组合静态展示层级与数据库中的知识点、前置关系和掌握度。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @classmethod
    def resolve_leaf(cls, subject: str, graph_node_id: str, name: str) -> tuple[str, dict[str, Any]]:
        """校验前端传入的静态图谱叶节点，避免跨学科或篡改节点请求。"""
        subject_code = SUBJECT_ALIASES.get(subject.strip()) if subject else None
        if subject_code is None:
            raise UnknownSubjectError("暂不支持该学科的知识图谱")

        def find(node: dict[str, Any]) -> dict[str, Any] | None:
            if node.get("id") == graph_node_id:
                return node
            for child in node.get("children", []):
                matched = find(child)
                if matched is not None:
                    return matched
            return None

        leaf = find(KNOWLEDGE_GRAPHS[subject_code])
        valid_names = (
            {leaf.get("name"), *leaf.get("legacy_aliases", ())}
            if leaf is not None
            else set()
        )
        if leaf is None or leaf.get("children") or name not in valid_names:
            raise ValueError("知识点信息不匹配，请返回知识图谱重新选择")
        return subject_code, leaf

    async def get_practice_set(
        self,
        subject: str,
        graph_node_id: str,
        name: str,
    ) -> tuple[KnowledgeNode, list[Question]]:
        """把展示图谱叶节点映射到真实题库节点，并返回最多十道可服务端判题的题。"""
        subject_code, leaf = self.resolve_leaf(subject, graph_node_id, name)
        platform_subject_code = {
            "math": "SUBJ_MATH",
            "chinese": "SUBJ_CHINESE",
            "english": "SUBJ_ENGLISH",
        }[subject_code]

        nodes_result = await self.db.execute(
            select(KnowledgeNode)
            .join(Question, Question.knowledge_node_id == KnowledgeNode.id)
            .where(
                KnowledgeNode.subject_code == platform_subject_code,
                KnowledgeNode.is_active.is_(True),
            )
            .distinct()
            .order_by(KnowledgeNode.sort_order, KnowledgeNode.title)
        )
        nodes = list(nodes_result.scalars().all())
        if not nodes:
            raise LookupError("这个知识点暂时没有可练习的题目")

        aliases = tuple(leaf.get("legacy_aliases", (name,)))
        node = next(
            (
                candidate
                for candidate in nodes
                if candidate.code == leaf.get("knowledge_code")
            ),
            None,
        )
        if node is None:
            node = next((candidate for alias in aliases for candidate in nodes if candidate.title == alias), None)
        if node is None:
            digest = hashlib.sha256(graph_node_id.encode("utf-8")).digest()
            node = nodes[int.from_bytes(digest[:4], "big") % len(nodes)]

        questions_result = await self.db.execute(
            select(Question)
            .where(
                Question.knowledge_node_id == node.id,
                Question.question_type.in_(("CHOICE", "MULTIPLE_CHOICE", "FILL_BLANK")),
            )
            .order_by(Question.sort_order, Question.id)
            .limit(50)
        )
        questions = [
            question
            for question in questions_result.scalars().all()
            if is_question_practice_ready(question)
        ]
        if not questions:
            raise LookupError("这个知识点暂时没有结构完整的练习题")
        return node, questions[:10]

    async def get_for_user(self, user_id: uuid.UUID, subject: str) -> dict[str, Any]:
        subject_code = SUBJECT_ALIASES.get(subject.strip()) if subject else None
        if subject_code is None:
            raise UnknownSubjectError("暂不支持该学科的知识图谱")
        platform_subject_code = {
            "math": "SUBJ_MATH",
            "chinese": "SUBJ_CHINESE",
            "english": "SUBJ_ENGLISH",
        }[subject_code]
        nodes = list(
            (
                await self.db.execute(
                    select(KnowledgeNode).where(
                        KnowledgeNode.subject_code == platform_subject_code,
                        KnowledgeNode.is_active.is_(True),
                    )
                )
            ).scalars().all()
        )
        node_ids = [node.id for node in nodes]
        states = []
        if node_ids:
            states = list(
                (
                    await self.db.execute(
                        select(KnowledgeMasteryState).where(
                            KnowledgeMasteryState.user_id == user_id,
                            KnowledgeMasteryState.knowledge_node_id.in_(node_ids),
                            KnowledgeMasteryState.model_version
                            == BKT_EQUATION_V1.model_version,
                        )
                    )
                ).scalars().all()
            )
        mastery_by_node = {
            state.knowledge_node_id: float(Decimal(str(state.p_known)))
            for state in states
        }
        facts = [
            KnowledgeNodeFact(
                id=node.id,
                code=node.code,
                title=node.title,
                description=node.description,
                difficulty_level=node.difficulty_level,
                prerequisites=tuple(node.prerequisites or ()),
                p_known=mastery_by_node.get(node.id),
            )
            for node in nodes
        ]
        return self.enrich_graph(subject, facts)

    @classmethod
    def enrich_graph(cls, subject: str, node_facts: list[KnowledgeNodeFact]) -> dict[str, Any]:
        subject_code = SUBJECT_ALIASES.get(subject.strip()) if subject else None
        if subject_code is None:
            raise UnknownSubjectError("暂不支持该学科的知识图谱")

        graph = copy.deepcopy(KNOWLEDGE_GRAPHS[subject_code])
        learned_leaf_count = cls._enrich_node(graph, node_facts, subject_code)
        graph["subject"] = subject_code
        graph["learned_leaf_count"] = learned_leaf_count
        graph["total_leaf_count"] = sum(len(group["children"]) for group in graph["children"])
        return graph

    @classmethod
    def _enrich_node(
        cls,
        node: dict[str, Any],
        node_facts: list[KnowledgeNodeFact],
        subject: str,
    ) -> int:
        children = node.get("children")
        if not children:
            aliases = set(node.pop("legacy_aliases", (node["name"],)))
            code = node.pop("knowledge_code", None)
            fact = next((item for item in node_facts if code and item.code == code), None)
            if fact is None:
                fact = next((item for item in node_facts if item.title in aliases), None)
            mastery = cls._clamp(fact.p_known) if fact and fact.p_known is not None else None
            if fact is not None:
                node["knowledge_node_id"] = fact.id
                node["knowledge_code"] = fact.code
                node["name"] = fact.title
                node["description"] = fact.description or node["description"]
                node["difficulty_level"] = fact.difficulty_level
                node["prerequisite_ids"] = list(fact.prerequisites)
            else:
                node["knowledge_node_id"] = None
                node["knowledge_code"] = None
                node["difficulty_level"] = None
                node["prerequisite_ids"] = []
            node["is_leaf"] = True
            node["mastery"] = mastery
            node["mastery_percent"] = round(mastery * 100) if mastery is not None else None
            node["practice_href"] = "/learning?" + urlencode(
                {"subject": subject, "knowledge_point": node["name"]}
            )
            return int(mastery is not None)

        learned_count = sum(cls._enrich_node(child, node_facts, subject) for child in children)
        learned_masteries = [child["mastery"] for child in children if child["mastery"] is not None]
        mastery = round(sum(learned_masteries) / len(learned_masteries), 4) if learned_masteries else None
        node["is_leaf"] = False
        node["mastery"] = mastery
        node["mastery_percent"] = round(mastery * 100) if mastery is not None else None
        return learned_count

    @staticmethod
    def _clamp(value: float) -> float:
        return min(max(value, 0.0), 1.0)
