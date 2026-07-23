"""AI 生成题批次的服务端判题、持久化与幂等重放。"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_generated import (
    GeneratedPracticeAnswer,
    GeneratedPracticeSubmission,
    GeneratedQuestion,
    GeneratedQuestionBatch,
)
from app.models.user import User
from app.schemas.question import GeneratedPracticeSubmitRequest
from app.services.behavior_service import BehaviorService
from app.services.gamification_service import reward_generated_practice_answer
from app.services.learning_service import judge_answer


logger = logging.getLogger(__name__)


def _payload_fingerprint(
    *,
    batch_id: uuid.UUID,
    request: GeneratedPracticeSubmitRequest,
) -> str:
    canonical = {
        "batch_id": str(batch_id),
        "answers": sorted(
            (
                {
                    "question_id": str(item.question_id),
                    "user_answer": item.user_answer.strip(),
                    "time_spent_seconds": item.time_spent_seconds,
                }
                for item in request.answers
            ),
            key=lambda item: item["question_id"],
        ),
    }
    encoded = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _submission_log_key(value: uuid.UUID) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


async def _build_response(
    db: AsyncSession,
    submission: GeneratedPracticeSubmission,
) -> dict:
    answers = await _submission_answers(db, submission.id)
    return {
        "submission_id": submission.id,
        "batch_id": submission.batch_id,
        "total_count": submission.total_count,
        "correct_count": submission.correct_count,
        "accuracy_rate": submission.accuracy_rate,
        "time_spent_seconds": submission.time_spent_seconds,
        "results": [
            {
                "question_id": answer.generated_question_id,
                "is_correct": answer.is_correct,
                "correct_answer": answer.correct_answer,
                "explanation": answer.explanation,
            }
            for answer in answers
        ],
        "gamification": submission.gamification or {},
    }


async def _submission_answers(
    db: AsyncSession,
    submission_id: uuid.UUID,
) -> list[GeneratedPracticeAnswer]:
    return list(
        (
            await db.execute(
                select(GeneratedPracticeAnswer)
                .where(GeneratedPracticeAnswer.submission_id == submission_id)
                .order_by(GeneratedPracticeAnswer.position)
            )
        ).scalars().all()
    )


async def submit_generated_practice(
    db: AsyncSession,
    *,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
    request: GeneratedPracticeSubmitRequest,
) -> dict:
    """校验批次所有权和精确题集后，原子持久化一次作答。"""
    batch = (
        await db.execute(
            select(GeneratedQuestionBatch)
            .where(
                GeneratedQuestionBatch.id == batch_id,
                GeneratedQuestionBatch.user_id == user_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在")

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": str(request.submission_id)},
    )
    existing = await db.get(GeneratedPracticeSubmission, request.submission_id)
    if existing is not None:
        if existing.user_id != user_id or existing.batch_id != batch_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="提交编号已用于不同的作答内容",
            )
        if existing.payload_fingerprint != _payload_fingerprint(
            batch_id=batch_id, request=request
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="提交编号已用于不同的作答内容",
            )
        logger.info(
            "AI 练习提交重放 submission_key=%s",
            _submission_log_key(request.submission_id),
        )
        return await _build_response(db, existing)

    if batch.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该批次尚未完成，无法提交",
        )

    questions = list(
        (
            await db.execute(
                select(GeneratedQuestion)
                .where(
                    GeneratedQuestion.batch_id == batch_id,
                    GeneratedQuestion.user_id == user_id,
                    GeneratedQuestion.quality_status == "passed",
                )
                .with_for_update()
            )
        ).scalars().all()
    )
    questions_by_id = {question.id: question for question in questions}
    submitted_ids = [item.question_id for item in request.answers]
    if (
        len(submitted_ids) != len(set(submitted_ids))
        or set(submitted_ids) != set(questions_by_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请完整且仅提交本批次已通过审核的每一道题",
        )

    fingerprint = _payload_fingerprint(batch_id=batch_id, request=request)
    user = (
        await db.execute(select(User).where(User.id == user_id).with_for_update())
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被删除")

    now = datetime.now(timezone.utc)
    total_time = sum(item.time_spent_seconds for item in request.answers)
    submission = GeneratedPracticeSubmission(
        id=request.submission_id,
        user_id=user_id,
        batch_id=batch_id,
        payload_fingerprint=fingerprint,
        total_count=len(request.answers),
        correct_count=0,
        accuracy_rate=0.0,
        time_spent_seconds=total_time,
        gamification={},
    )
    db.add(submission)
    await db.flush()

    correct_count = 0
    reward_payloads = []
    for position, submitted in enumerate(request.answers):
        question = questions_by_id[submitted.question_id]
        is_correct = judge_answer(question, submitted.user_answer)
        correct_count += int(is_correct)
        answer = GeneratedPracticeAnswer(
            submission_id=submission.id,
            generated_question_id=question.id,
            position=position,
            user_answer=submitted.user_answer,
            is_correct=is_correct,
            correct_answer=question.correct_answer,
            explanation=question.explanation,
            time_spent_seconds=submitted.time_spent_seconds,
            answered_at=now,
        )
        db.add(answer)
        await db.flush()
        await BehaviorService(db).update_after_answer(
            user_id=user_id,
            answer_id=answer.id,
            question=question,
            is_correct=is_correct,
            response_time_ms=submitted.time_spent_seconds * 1000,
            answered_at=now,
        )
        reward_payloads.append(
            await reward_generated_practice_answer(
                db, user=user, answer=answer, question=question
            )
        )

    latest_reward = reward_payloads[-1] if reward_payloads else {}
    achievements = []
    seen_achievements = set()
    for payload in reward_payloads:
        for achievement in payload.get("new_achievements", []):
            if achievement["id"] not in seen_achievements:
                seen_achievements.add(achievement["id"])
                achievements.append(achievement)
    submission.correct_count = correct_count
    submission.accuracy_rate = correct_count / len(request.answers)
    submission.gamification = {
        "points_earned": sum(item.get("points_earned", 0) for item in reward_payloads),
        "base_points": sum(item.get("base_points", 0) for item in reward_payloads),
        "streak_bonus": sum(item.get("streak_bonus", 0) for item in reward_payloads),
        "total_points": latest_reward.get("total_points", user.total_score or 0),
        "level": latest_reward.get("level", 1),
        "streak": latest_reward.get("streak", user.current_correct_streak or 0),
        "new_achievements": achievements,
    }
    await db.flush()
    logger.info(
        "AI 练习提交已持久化 submission_key=%s total=%s correct=%s",
        _submission_log_key(request.submission_id),
        submission.total_count,
        submission.correct_count,
    )
    return await _build_response(db, submission)
