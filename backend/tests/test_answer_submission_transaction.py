"""答题提交的真实事务、行锁和幂等回归。"""

import asyncio
from datetime import date, datetime, timezone
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.content import AgeGroup, KnowledgeNode, Question, Subject
from app.models.learning import LearningSession
from app.models.user import User
from app.services.learning_service import complete_session, submit_answer


@pytest.mark.asyncio
async def test_concurrent_answers_same_session_preserve_counts_and_rewards(db_session, monkeypatch):
    user_id = uuid.uuid4()
    node_id = uuid.uuid4()
    question_id = uuid.uuid4()
    session_id = uuid.uuid4()
    await db_session.merge(Subject(code="SUBJ_P003", name="并发测试", sort_order=0))
    await db_session.merge(AgeGroup(code="AGE_P003", name="测试年龄", min_age=10, max_age=12, theme_config={}))
    db_session.add_all([
        User(
            id=user_id, nickname="并发学生", email=f"p005-{user_id}@example.test",
            password_hash="hash", birth_date=date(2012, 1, 1), age_group="AGE_P003",
        ),
        KnowledgeNode(
            id=node_id, title="并发知识点", subject_code="SUBJ_P003", age_group_code="AGE_P003",
            difficulty_level="DIFF_EASY", content_type="TYPE_QUIZ", content_body="测试",
        ),
    ])
    await db_session.flush()
    db_session.add_all([
        Question(
            id=question_id, knowledge_node_id=node_id, difficulty_level="DIFF_EASY",
            question_type="CHOICE", question_body="1+1=?", options=[{"key": "A", "value": "2"}],
            correct_answer="A", explanation="测试",
        ),
        LearningSession(
            id=session_id, user_id=user_id, knowledge_node_id=node_id,
            difficulty_level="DIFF_EASY", status="in_progress",
            started_at=datetime.now(timezone.utc),
        ),
    ])
    await db_session.commit()

    session_factory = async_sessionmaker(
        db_session.bind, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def submit(answer_id: uuid.UUID):
        async with session_factory() as session:
            result = await submit_answer(
                session, session_id, user_id, question_id, answer_id, "A", 3
            )
            await session.commit()
            return result

    results = await asyncio.gather(submit(uuid.uuid4()), submit(uuid.uuid4()))
    assert {result["is_correct"] for result in results} == {True}

    user = await db_session.get(User, user_id)
    learning_session = await db_session.get(LearningSession, session_id)
    assert learning_session.total_questions == 2
    assert learning_session.correct_count == 2
    assert user.total_answered == 2
    assert user.correct_answered == 2
    assert (
        await db_session.execute(
            text("SELECT COUNT(*) FROM gamification_events WHERE user_id=:id"),
            {"id": user_id},
        )
    ).scalar_one() == 2

    replay_id = uuid.uuid4()
    async with session_factory() as session:
        await submit_answer(session, session_id, user_id, question_id, replay_id, "A", 3)
        await session.commit()
    async with session_factory() as session:
        replay = await submit_answer(session, session_id, user_id, question_id, replay_id, "A", 3)
        await session.commit()
    assert replay["gamification"]["replayed"] is True
    await db_session.refresh(await db_session.get(LearningSession, session_id))
    assert (await db_session.get(LearningSession, session_id)).total_questions == 3

    # 全局 answer_id 在不同会话并发时只能成功一次，另一请求应得到可解释的冲突而非 500。
    second_session_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(LearningSession(
            id=second_session_id, user_id=user_id, knowledge_node_id=node_id,
            difficulty_level="DIFF_EASY", status="in_progress",
            started_at=datetime.now(timezone.utc),
        ))
        await session.commit()

    shared_id = uuid.uuid4()

    async def submit_shared(target_session_id):
        async with session_factory() as session:
            try:
                result = await submit_answer(
                    session, target_session_id, user_id, question_id, shared_id, "A", 3
                )
                await session.commit()
                return result
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    shared_results = await asyncio.gather(
        submit_shared(session_id), submit_shared(second_session_id)
    )
    assert sum(isinstance(item, dict) for item in shared_results) == 1
    assert 409 in shared_results

    from app.services.wrong_book_service import WrongBookService

    async def fail_wrong_book(*_args, **_kwargs):
        raise RuntimeError("injected wrong-book failure")

    monkeypatch.setattr(WrongBookService, "record_wrong_answer", fail_wrong_book)
    failed_id = uuid.uuid4()
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="injected"):
            await submit_answer(session, session_id, user_id, question_id, failed_id, "B", 3)
        await session.rollback()
    assert (
        await db_session.execute(
            text("SELECT COUNT(*) FROM answers WHERE id=:id"), {"id": failed_id}
        )
    ).scalar_one() == 0


@pytest.mark.asyncio
async def test_completed_owned_learning_session_can_be_completed_again(db_session):
    user_id, node_id, session_id = (uuid.uuid4() for _ in range(3))
    completed_at = datetime.now(timezone.utc)
    await db_session.merge(Subject(code="SUBJ_COMPLETE", name="完成重放", sort_order=0))
    await db_session.merge(AgeGroup(code="AGE_CMP", name="完成重放", min_age=10, max_age=12, theme_config={}))
    db_session.add_all([
        User(
            id=user_id, nickname="完成重放用户", email=f"complete-{user_id}@example.test",
            password_hash="hash", birth_date=date(2012, 1, 1), age_group="AGE_CMP",
        ),
        KnowledgeNode(
            id=node_id, title="完成重放", subject_code="SUBJ_COMPLETE", age_group_code="AGE_CMP",
            difficulty_level="DIFF_EASY", content_type="TYPE_QUIZ", content_body="测试",
        ),
    ])
    await db_session.flush()
    session = LearningSession(
        id=session_id, user_id=user_id, knowledge_node_id=node_id,
        difficulty_level="DIFF_EASY", status="completed",
        started_at=completed_at, completed_at=completed_at,
        total_questions=2, correct_count=1,
    )
    db_session.add(session)
    await db_session.flush()

    replayed = await complete_session(db_session, session_id, user_id)

    assert replayed is session
    assert replayed.status == "completed"
    assert replayed.completed_at == completed_at
