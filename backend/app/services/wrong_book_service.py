"""错题本的事务内收录、筛选和复习服务。"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.content import KnowledgeNode, Question
from app.models.wrong_book import WrongPracticeAttempt, WrongQuestion, WrongQuestionEvent
from app.services.question_access import verified_answer_feedback


SCHEDULER_VERSION = "v1"
logger = logging.getLogger(__name__)


def _immutable_practice_fingerprint(
    question_id: uuid.UUID, user_answer: str
) -> str:
    payload = json.dumps(
        {"question_id": str(question_id), "user_answer": user_answer.strip()},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _attempt_log_key(value: uuid.UUID) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def calculate_next_review_at(*, now: datetime, is_correct: bool, review_count: int, difficulty_factor: float = 1.0) -> datetime:
    """Deterministic interval scheduler; inputs are explicit for reproducible tests."""
    intervals = (1, 3, 7, 14, 30)
    index = min(max(review_count, 0), len(intervals) - 1)
    days = intervals[index] if is_correct else 1
    return now + timedelta(days=max(1, round(days * max(0.5, difficulty_factor))))


class WrongBookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_wrong_answer(self, user_id: uuid.UUID, question_id: uuid.UUID, answer_id: uuid.UUID, subject: str, wrong_answer: str = "") -> WrongQuestion | None:
        """仅处理一次正式 Answer 事件；重复请求不会改变错题计数。"""
        event_result = await self.db.execute(
            insert(WrongQuestionEvent).values(answer_id=answer_id, user_id=user_id, question_id=question_id)
            .on_conflict_do_nothing(index_elements=[WrongQuestionEvent.answer_id])
            .returning(WrongQuestionEvent.id)
        )
        if event_result.scalar_one_or_none() is None:
            return None
        now = datetime.now(timezone.utc)
        statement = insert(WrongQuestion).values(
            user_id=user_id,
            question_id=question_id,
            subject=subject,
            wrong_count=1,
            first_wrong_at=now,
            last_wrong_at=now,
            last_wrong_answer=wrong_answer,
            is_mastered=False,
            review_count=0,
            scheduler_version=SCHEDULER_VERSION,
            difficulty_factor=100,
            next_review_at=now + timedelta(days=1),
        ).on_conflict_do_update(
            constraint="uq_wrong_question_user_question",
            set_={
                "wrong_count": WrongQuestion.wrong_count + 1,
                "last_wrong_at": now,
                "last_wrong_answer": wrong_answer,
                "is_mastered": False,
                "mastered_at": None,
                "updated_at": now,
                "next_review_at": now + timedelta(days=1),
                "scheduler_version": SCHEDULER_VERSION,
                "difficulty_factor": 100,
            },
        ).returning(WrongQuestion)
        result = await self.db.execute(statement)
        wrong_question = result.scalar_one()
        await self.db.flush()
        return wrong_question

    async def submit_practice_answer(
        self,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        user_answer: str,
        *,
        attempt_id: uuid.UUID,
    ) -> dict:
        """服务端判定错题重练，确认题目归属后才返回答案与解析。"""
        if isinstance(self.db, AsyncSession):
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": str(attempt_id)},
            )
        existing = await self.db.get(WrongPracticeAttempt, attempt_id)
        if existing is not None:
            if existing.user_id != user_id or existing.question_id != question_id:
                logger.info(
                    "Wrong practice attempt result=conflict attempt_key=%s",
                    _attempt_log_key(attempt_id),
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="练习尝试编号已用于不同的作答内容",
                )
            if existing.payload_fingerprint != _immutable_practice_fingerprint(
                question_id, user_answer
            ):
                logger.info(
                    "Wrong practice attempt result=conflict attempt_key=%s",
                    _attempt_log_key(attempt_id),
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="练习尝试编号已用于不同的作答内容",
                )
            logger.info(
                "Wrong practice attempt result=replayed attempt_key=%s",
                _attempt_log_key(attempt_id),
            )
            return dict(existing.result_payload)

        result = await self.db.execute(
            select(WrongQuestion).options(joinedload(WrongQuestion.question)).where(
                WrongQuestion.user_id == user_id,
                WrongQuestion.question_id == question_id,
                WrongQuestion.is_mastered.is_(False),
            ).with_for_update(of=WrongQuestion)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return {"found": False}
        from app.services.learning_service import judge_answer
        is_correct = judge_answer(record.question, user_answer)
        response = {
            "found": True,
            **verified_answer_feedback(
                record.question,
                verified_question_id=question_id,
                is_correct=is_correct,
            ),
        }
        self.db.add(
            WrongPracticeAttempt(
                id=attempt_id,
                user_id=user_id,
                question_id=question_id,
                payload_fingerprint=_immutable_practice_fingerprint(
                    question_id, user_answer
                ),
                result_payload=response,
            )
        )
        # 先固化幂等结果，再改变复习调度字段。
        await self.db.flush()
        record.review_count += 1
        current_factor = getattr(record, "difficulty_factor", 100)
        record.difficulty_factor = min(150, current_factor + 10) if is_correct else max(50, current_factor - 20)
        record.scheduler_version = SCHEDULER_VERSION
        record.next_review_at = calculate_next_review_at(
            now=datetime.now(timezone.utc),
            is_correct=is_correct,
            review_count=record.review_count,
            difficulty_factor=record.difficulty_factor / 100,
        )
        if is_correct and record.review_count >= 5:
            record.is_mastered = True
            record.mastered_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info(
            "Wrong practice attempt result=created attempt_key=%s",
            _attempt_log_key(attempt_id),
        )
        return response

    async def list_questions(self, user_id: uuid.UUID, subject: str | None, knowledge_point: str | None, is_mastered: bool | None, page: int, page_size: int) -> tuple[list[WrongQuestion], int]:
        filters = [WrongQuestion.user_id == user_id]
        if subject:
            filters.append(WrongQuestion.subject == subject)
        if is_mastered is not None:
            filters.append(WrongQuestion.is_mastered == is_mastered)
        statement = select(WrongQuestion).options(
            joinedload(WrongQuestion.question).joinedload(Question.knowledge_node_rel)
        ).where(*filters)
        count_statement = select(func.count(WrongQuestion.id)).where(*filters)
        if knowledge_point:
            statement = statement.join(Question, WrongQuestion.question_id == Question.id).join(KnowledgeNode, Question.knowledge_node_id == KnowledgeNode.id).where(func.lower(KnowledgeNode.title).contains(knowledge_point.lower()))
            count_statement = count_statement.select_from(WrongQuestion).join(Question, WrongQuestion.question_id == Question.id).join(KnowledgeNode, Question.knowledge_node_id == KnowledgeNode.id).where(func.lower(KnowledgeNode.title).contains(knowledge_point.lower()))
        total = (await self.db.execute(count_statement)).scalar_one()
        result = await self.db.execute(statement.order_by(desc(WrongQuestion.last_wrong_at)).offset((page - 1) * page_size).limit(page_size))
        return list(result.scalars().unique().all()), total

    async def mark_mastered(self, user_id: uuid.UUID, question_id: uuid.UUID) -> bool:
        result = await self.db.execute(select(WrongQuestion).where(WrongQuestion.user_id == user_id, WrongQuestion.question_id == question_id))
        record = result.scalar_one_or_none()
        if record is None:
            return False
        record.is_mastered = True
        record.mastered_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def get_practice_questions(self, user_id: uuid.UUID, subject: str | None, count: int) -> list[Question]:
        statement = select(Question).join(WrongQuestion, WrongQuestion.question_id == Question.id).where(WrongQuestion.user_id == user_id, WrongQuestion.is_mastered.is_(False), WrongQuestion.next_review_at <= datetime.now(timezone.utc))
        if subject:
            statement = statement.where(WrongQuestion.subject == subject)
        result = await self.db.execute(statement.order_by(WrongQuestion.next_review_at, desc(WrongQuestion.wrong_count)).limit(count))
        return list(result.scalars().all())

    async def get_stats(self, user_id: uuid.UUID) -> dict:
        base = WrongQuestion.user_id == user_id
        total = (await self.db.execute(select(func.count(WrongQuestion.id)).where(base))).scalar_one()
        mastered = (await self.db.execute(select(func.count(WrongQuestion.id)).where(base, WrongQuestion.is_mastered.is_(True)))).scalar_one()
        rows = await self.db.execute(select(WrongQuestion.subject, func.count(WrongQuestion.id)).where(base, WrongQuestion.is_mastered.is_(False)).group_by(WrongQuestion.subject))
        now = datetime.now(timezone.utc)
        need_review = (await self.db.execute(select(func.count(WrongQuestion.id)).where(base, WrongQuestion.is_mastered.is_(False), WrongQuestion.next_review_at <= now))).scalar_one()
        return {"total": total, "mastered": mastered, "unmastered": total - mastered, "by_subject": {subject: count for subject, count in rows.all()}, "need_review_today": need_review}
