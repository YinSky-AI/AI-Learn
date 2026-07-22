"""可恢复管理变更与同事务脱敏审计。"""

from dataclasses import dataclass
import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AdminChangeResult:
    changed: bool
    status: str
    message: str
    impact_scope: dict[str, int]


_SPECS = {
    "user": ("users", "uuid"),
    "course": ("courses", "uuid"),
    "lesson": ("lessons", "uuid"),
    "question": ("questions", "int"),
}

_IMPACT_QUERIES = {
    "user": {
        "user_courses": "SELECT COUNT(*) FROM user_courses WHERE user_id=:id",
        "user_lessons": "SELECT COUNT(*) FROM user_lessons WHERE user_id=:id",
        "learning_sessions": "SELECT COUNT(*) FROM learning_sessions WHERE user_id=:id",
        "answers": "SELECT COUNT(*) FROM answers a JOIN learning_sessions s ON s.id=a.session_id WHERE s.user_id=:id",
        "wrong_questions": "SELECT COUNT(*) FROM wrong_questions WHERE user_id=:id",
        "wrong_question_events": "SELECT COUNT(*) FROM wrong_question_events WHERE user_id=:id",
        "chat_messages": "SELECT COUNT(*) FROM chat_messages WHERE user_id=:id",
        "gamification_events": "SELECT COUNT(*) FROM gamification_events WHERE user_id=:id",
        "user_achievements": "SELECT COUNT(*) FROM user_achievements WHERE user_id=:id",
        "daily_challenge_attempts": "SELECT COUNT(*) FROM daily_challenge_attempts WHERE user_id=:id",
        "generated_question_batches": "SELECT COUNT(*) FROM generated_question_batches WHERE user_id=:id",
        "generated_questions": "SELECT COUNT(*) FROM generated_questions WHERE user_id=:id",
        "harness_runs": "SELECT COUNT(*) FROM harness_runs WHERE user_id=:id",
        "session_memories": "SELECT COUNT(*) FROM session_memories WHERE user_id=:id",
    },
    "course": {
        "lessons": "SELECT COUNT(*) FROM lessons WHERE course_id=:id",
        "user_courses": "SELECT COUNT(*) FROM user_courses WHERE course_id=:id",
        "user_lessons": "SELECT COUNT(*) FROM user_lessons WHERE course_id=:id",
        "chat_messages": "SELECT COUNT(*) FROM chat_messages WHERE course_id=:id",
    },
    "lesson": {
        "user_lessons": "SELECT COUNT(*) FROM user_lessons WHERE lesson_id=:id",
        "chat_messages": "SELECT COUNT(*) FROM chat_messages WHERE lesson_id=:id",
    },
    "question": {
        "question_knowledge": "SELECT COUNT(*) FROM question_knowledge WHERE question_id=:id",
        "question_stats": "SELECT COUNT(*) FROM question_stats WHERE question_id=:id",
    },
}


class AdminChangeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def change(self, *, action: str, entity_type: str, entity_id: str, actor_id: uuid.UUID, reason: str, request_id: str) -> AdminChangeResult:
        if action not in {"soft_delete", "restore"} or entity_type not in _SPECS:
            await self._write_audit(
                actor_id=actor_id, action=str(action)[:30], entity_type=str(entity_type)[:30],
                entity_id=str(entity_id)[:64], reason="[非法管理请求]", status="rejected",
                request_id=request_id, before={"state": "invalid_request"},
                after={"state": "unchanged"}, impact={},
            )
            raise ValueError("不支持的管理变更")
        reason = reason.strip()
        table, id_kind = _SPECS[entity_type]
        if not 5 <= len(reason) <= 500:
            await self._write_audit(
                actor_id=actor_id, action=action, entity_type=entity_type,
                entity_id=entity_id, reason="[未提供有效原因]", status="rejected",
                request_id=request_id, before={"state": "invalid_request"},
                after={"state": "unchanged"}, impact={},
            )
            raise ValueError("请提供 5 到 500 字的变更原因")
        try:
            normalized_id = int(entity_id) if id_kind == "int" else uuid.UUID(entity_id)
        except (ValueError, TypeError):
            await self._write_audit(
                actor_id=actor_id, action=action, entity_type=entity_type,
                entity_id=str(entity_id)[:64], reason=reason, status="rejected",
                request_id=request_id, before={"state": "invalid_identifier"},
                after={"state": "unchanged"}, impact={},
            )
            raise ValueError("目标 ID 格式无效") from None

        selected_columns = "deleted_at, course_id" if entity_type == "lesson" else "deleted_at"
        row = (await self.db.execute(
            text(f"SELECT {selected_columns} FROM {table} WHERE id=:id FOR UPDATE"), {"id": normalized_id}
        )).mappings().one_or_none()
        current = "missing" if row is None else ("deleted" if row["deleted_at"] else "active")
        desired = "deleted" if action == "soft_delete" else "active"
        impact = {}
        if row is not None:
            for impact_name, query in _IMPACT_QUERIES[entity_type].items():
                impact[impact_name] = int((await self.db.execute(
                    text(query), {"id": normalized_id}
                )).scalar_one())
        changed = row is not None and current != desired
        status = "succeeded" if changed else "rejected"
        if changed:
            value = "NOW()" if desired == "deleted" else "NULL"
            updated = ", updated_at=NOW()" if table != "questions" else ""
            await self.db.execute(text(f"UPDATE {table} SET deleted_at={value}{updated} WHERE id=:id"), {"id": normalized_id})
            if entity_type == "user":
                await self.db.execute(
                    text(
                        "UPDATE users SET credential_version = credential_version + 1, "
                        "credentials_revoked_at = NOW() WHERE id=:id"
                    ),
                    {"id": normalized_id},
                )
            if entity_type == "lesson":
                await self.db.execute(
                    text(
                        "UPDATE courses SET total_lessons = ("
                        "SELECT COUNT(*) FROM lessons "
                        "WHERE course_id=:course_id AND is_active=true AND deleted_at IS NULL"
                        "), updated_at=NOW() WHERE id=:course_id"
                    ),
                    {"course_id": row["course_id"]},
                )
        before = {"state": current, "entity_type": entity_type}
        after = {"state": desired if changed else current, "entity_type": entity_type}
        await self._write_audit(
            actor_id=actor_id, action=action, entity_type=entity_type,
            entity_id=str(entity_id), reason=reason, status=status,
            request_id=request_id, before=before, after=after, impact=impact,
        )
        if changed:
            message = "已移入可恢复状态" if desired == "deleted" else "已恢复"
        elif current == "missing":
            message = "目标不存在"
        else:
            message = "目标已经处于该状态，未重复变更"
        return AdminChangeResult(changed, status, message, impact)

    async def _write_audit(
        self, *, actor_id: uuid.UUID, action: str, entity_type: str,
        entity_id: str, reason: str, status: str, request_id: str,
        before: dict, after: dict, impact: dict[str, int],
    ) -> None:
        await self.db.execute(
            text(
                "INSERT INTO admin_change_audits "
                "(actor_id, action, entity_type, entity_id, reason, status, request_id, before_summary, after_summary, impact_scope) "
                "VALUES (:actor, :action, :type, :id, :reason, :status, :request, CAST(:before AS jsonb), CAST(:after AS jsonb), CAST(:impact AS jsonb))"
            ),
            {"actor": actor_id, "action": action, "type": entity_type, "id": str(entity_id), "reason": reason,
             "status": status, "request": request_id[:100], "before": json.dumps(before), "after": json.dumps(after), "impact": json.dumps(impact)},
        )
