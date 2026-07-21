"""错题本的事务内收录、筛选和复习服务。"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.content import KnowledgeNode, Question
from app.models.wrong_book import WrongQuestion


class WrongBookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_wrong_question(self, user_id: uuid.UUID, question_id: uuid.UUID, subject: str, wrong_answer: str = "") -> WrongQuestion:
        """原子化收录错题，避免并发答题时的查询-插入竞争。"""
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
        ).on_conflict_do_update(
            constraint="uq_wrong_question_user_question",
            set_={
                "wrong_count": WrongQuestion.wrong_count + 1,
                "last_wrong_at": now,
                "last_wrong_answer": wrong_answer,
                "is_mastered": False,
                "mastered_at": None,
                "updated_at": now,
            },
        ).returning(WrongQuestion)
        result = await self.db.execute(statement)
        wrong_question = result.scalar_one()
        await self.db.flush()
        return wrong_question

    async def list_questions(self, user_id: uuid.UUID, subject: str | None, knowledge_point: str | None, is_mastered: bool | None, page: int, page_size: int) -> tuple[list[WrongQuestion], int]:
        filters = [WrongQuestion.user_id == user_id]
        if subject:
            filters.append(WrongQuestion.subject == subject)
        if is_mastered is not None:
            filters.append(WrongQuestion.is_mastered == is_mastered)
        statement = select(WrongQuestion).options(joinedload(WrongQuestion.question)).where(*filters)
        count_statement = select(func.count(WrongQuestion.id)).where(*filters)
        if knowledge_point:
            statement = statement.join(Question, WrongQuestion.question_id == Question.id).join(KnowledgeNode, Question.knowledge_node_id == KnowledgeNode.id).where(func.lower(KnowledgeNode.title).contains(knowledge_point.lower()))
            count_statement = count_statement.select_from(WrongQuestion).join(Question, WrongQuestion.question_id == Question.id).join(KnowledgeNode, Question.knowledge_node_id == KnowledgeNode.id).where(func.lower(KnowledgeNode.title).contains(knowledge_point.lower()))
        total = (await self.db.execute(count_statement)).scalar_one()
        result = await self.db.execute(statement.order_by(desc(WrongQuestion.last_wrong_at)).offset((page - 1) * page_size).limit(page_size))
        return list(result.scalalars().unique().all()), total

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
        statement = select(Question).join(WrongQuestion, WrongQuestion.question_id == Question.id).where(WrongQuestion.user_id == user_id, WrongQuestion.is_mastered.is_(False))
        if subject:
            statement = statement.where(WrongQuestion.subject == subject)
        result = await self.db.execute(statement.order_by(desc(WrongQuestion.wrong_count), func.random()).limit(count))
        return list(result.scalars().all())

    async def get_stats(self, user_id: uuid.UUID) -> dict:
        base = WrongQuestion.user_id == user_id
        total = (await self.db.execute(select(func.count(WrongQuestion.id)).where(base))).scalar_one()
        mastered = (await self.db.execute(select(func.count(WrongQuestion.id)).where(base, WrongQuestion.is_mastered.is_(True)))).scalar_one()
        rows = await self.db.execute(select(WrongQuestion.subject, func.count(WrongQuestion.id)).where(base, WrongQuestion.is_mastered.is_(False)).group_by(WrongQuestion.subject))
        need_review = (await self.db.execute(select(func.count(WrongQuestion.id)).where(base, WrongQuestion.is_mastered.is_(False), WrongQuestion.last_wrong_at >= datetime.now(timezone.utc) - timedelta(days=3)))).scalar_one()
        return {"total": total, "mastered": mastered, "unmastered": total - mastered, "by_subject": {subject: count for subject, count in rows.all()}, "need_review_today": need_review}
