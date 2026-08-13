"""学习行为建模与个人学习报告服务。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class BehaviorService:
    """将已持久化的答题事件投影到用户自己的行为画像中。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _profile(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = None
        profile = dict(value) if isinstance(value, dict) else {}
        profile.setdefault("knowledge_mastery", {})
        profile.setdefault("subject_mastery", {})
        profile.setdefault("study_stats", {"total_time_minutes": 0.0, "daily_records": {}})
        profile["study_stats"].setdefault("total_time_minutes", 0.0)
        profile["study_stats"].setdefault("daily_records", {})
        profile.setdefault("processed_answer_ids", [])
        return profile

    async def update_after_answer(
        self,
        *,
        user_id: uuid.UUID,
        answer_id: uuid.UUID,
        question: Any,
        is_correct: bool,
        response_time_ms: int = 0,
        answered_at: datetime | None = None,
    ) -> dict[str, Any]:
        """更新画像；相同的已持久化 answer_id 只会消费一次。"""
        user = await self.db.get(User, user_id)
        if user is None:
            return {}

        profile = self._profile(user.behavior_profile)
        event_id = str(answer_id)
        if event_id in profile["processed_answer_ids"]:
            return profile

        node = getattr(question, "knowledge_node_rel", None)
        subject = (
            getattr(node, "subject_code", None)
            or getattr(question, "subject_code", None)
            or "未分类"
        )
        event_time = answered_at or datetime.now(timezone.utc)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        subject_data = profile["subject_mastery"].setdefault(subject, {"level": 0.5, "total": 0, "correct": 0})
        subject_data["total"] += 1
        subject_data["correct"] += int(is_correct)
        subject_data["level"] = round(subject_data["correct"] / subject_data["total"], 4)

        date_key = event_time.date().isoformat()
        daily = profile["study_stats"]["daily_records"].setdefault(date_key, {"answered": 0, "correct": 0, "time_minutes": 0.0})
        minutes = max(response_time_ms, 0) / 60_000
        daily["answered"] += 1
        daily["correct"] += int(is_correct)
        daily["time_minutes"] = round(float(daily.get("time_minutes", 0)) + minutes, 2)
        profile["study_stats"]["total_time_minutes"] = round(float(profile["study_stats"].get("total_time_minutes", 0)) + minutes, 2)

        # 保留足够的幂等键，同时限制 JSONB 无界增长。
        profile["processed_answer_ids"] = (profile["processed_answer_ids"] + [event_id])[-3000:]
        user.behavior_profile = profile
        await self.db.flush()
        return profile

    async def get_learning_report(self, user_id: uuid.UUID, days: int = 30, now: datetime | None = None) -> dict[str, Any]:
        """读取当前用户自己的报告，不跨用户聚合任何答题数据。"""
        user = await self.db.get(User, user_id)
        if user is None:
            return self.empty_report(days, now)
        profile = self._profile(user.behavior_profile)
        return self._report(profile, days, now)

    @classmethod
    def empty_report(cls, days: int, now: datetime | None = None) -> dict[str, Any]:
        return cls._report(cls._profile({}), days, now)

    @staticmethod
    def _report(profile: dict[str, Any], days: int, now: datetime | None) -> dict[str, Any]:
        days = min(max(days, 1), 90)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        subjects = [
            {"subject": name, "level": float(data.get("level", 0)), "total": int(data.get("total", 0)), "correct": int(data.get("correct", 0))}
            for name, data in profile["subject_mastery"].items()
        ]
        subjects.sort(key=lambda item: item["level"], reverse=True)
        total_answered = sum(item["total"] for item in subjects)
        total_correct = sum(item["correct"] for item in subjects)
        knowledge = [
            {"point": name, "level": float(data.get("level", 0)), "total": int(data.get("total", 0))}
            for name, data in profile["knowledge_mastery"].items()
        ]
        knowledge.sort(key=lambda item: item["level"])
        weak = [
            {**item, "suggestion": f"建议针对“{item['point']}”完成基础练习并复盘错题。"}
            for item in knowledge if item["total"] >= 2
        ][:5]
        strong = [item for item in reversed(knowledge) if item["level"] >= 0.7][:5]
        records = profile["study_stats"]["daily_records"]
        trend = []
        for offset in range(days - 1, -1, -1):
            date_key = (current - timedelta(days=offset)).date().isoformat()
            item = records.get(date_key, {})
            trend.append({"date": date_key, "answered": int(item.get("answered", 0)), "correct": int(item.get("correct", 0))})
        return {
            "overview": {
                "total_answered": total_answered,
                "correct_rate": round(total_correct / total_answered, 3) if total_answered else 0.0,
                "study_days": len(records),
                "total_time_minutes": round(float(profile["study_stats"].get("total_time_minutes", 0)), 1),
            },
            "subject_mastery": subjects,
            "weak_points": weak,
            "strong_points": strong,
            "daily_trend": trend,
            "knowledge_heatmap": {item["point"]: item["level"] for item in knowledge},
        }
