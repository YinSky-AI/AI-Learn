"""为当前用户生成带掌握度的知识图谱。"""

from __future__ import annotations

import copy
import uuid
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.knowledge_graph import KNOWLEDGE_GRAPHS, SUBJECT_ALIASES
from app.services.behavior_service import BehaviorService


class UnknownSubjectError(ValueError):
    """请求的学科尚未进入知识图谱 MVP。"""


class KnowledgeGraphService:
    """组合静态知识结构与行为报告中的用户掌握度。"""

    def __init__(self, db: AsyncSession):
        self.db = db

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
