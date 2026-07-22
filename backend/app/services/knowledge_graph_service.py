"""为当前用户生成带掌握度的知识图谱。"""

from __future__ import annotations

import copy
import hashlib
import uuid
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.knowledge_graph import KNOWLEDGE_GRAPHS, SUBJECT_ALIASES
from app.models.content import KnowledgeNode, Question
from app.services.behavior_service import BehaviorService
from app.services.content_service import is_question_practice_ready


class UnknownSubjectError(ValueError):
    """请求的学科尚未进入知识图谱 MVP。"""


class KnowledgeGraphService:
    """组合静态知识结构与行为报告中的用户掌握度。"""

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
        if leaf is None or leaf.get("children") or leaf.get("name") != name:
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

        aliases = tuple(leaf.get("mastery_keys", (name,)))
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
        report = await BehaviorService(self.db).get_learning_report(user_id, days=30)
        return self.enrich_graph(subject, report["knowledge_heatmap"])

    @classmethod
    def enrich_graph(cls, subject: str, mastery_map: dict[str, float]) -> dict[str, Any]:
        subject_code = SUBJECT_ALIASES.get(subject.strip()) if subject else None
        if subject_code is None:
            raise UnknownSubjectError("暂不支持该学科的知识图谱")

        graph = copy.deepcopy(KNOWLEDGE_GRAPHS[subject_code])
        learned_leaf_count = cls._enrich_node(graph, mastery_map, subject_code)
        graph["subject"] = subject_code
        graph["learned_leaf_count"] = learned_leaf_count
        graph["total_leaf_count"] = sum(len(group["children"]) for group in graph["children"])
        return graph

    @classmethod
    def _enrich_node(cls, node: dict[str, Any], mastery_map: dict[str, float], subject: str) -> int:
        children = node.get("children")
        if not children:
            keys = dict.fromkeys(node.pop("mastery_keys", (node["name"],)))
            values = [cls._clamp(float(mastery_map[key])) for key in keys if key in mastery_map]
            mastery = round(sum(values) / len(values), 4) if values else None
            node["is_leaf"] = True
            node["mastery"] = mastery
            node["mastery_percent"] = round(mastery * 100) if mastery is not None else None
            node["practice_href"] = "/learning?" + urlencode(
                {"subject": subject, "knowledge_point": node["name"]}
            )
            return int(mastery is not None)

        learned_count = sum(cls._enrich_node(child, mastery_map, subject) for child in children)
        learned_masteries = [child["mastery"] for child in children if child["mastery"] is not None]
        mastery = round(sum(learned_masteries) / len(learned_masteries), 4) if learned_masteries else None
        node["is_leaf"] = False
        node["mastery"] = mastery
        node["mastery_percent"] = round(mastery * 100) if mastery is not None else None
        return learned_count

    @staticmethod
    def _clamp(value: float) -> float:
        return min(max(value, 0.0), 1.0)
