"""Deterministic candidate ranking and adaptive next-question selection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adaptive_learning import AdaptationDecision, AnswerDiagnosis
from app.models.ai_generated import (
    GeneratedPracticeAnswer,
    GeneratedPracticeSubmission,
    GeneratedQuestion,
)
from app.models.content import KnowledgeNode, Question
from app.models.learning import Answer, LearningSession
from app.services.question_generation_service import (
    enqueue_standard_variant_job,
    enqueue_variant_job,
)
from app.services.question_access import sanitize_public_value
from app.services.content_service import is_question_practice_ready


@dataclass(frozen=True, slots=True)
class AdaptiveQuestionCandidate:
    source: str
    question_id: uuid.UUID
    misconception_match: bool
    knowledge_match: bool
    difficulty_match: bool
    last_exposure_at: datetime | None


def rank_candidates(
    candidates: list[AdaptiveQuestionCandidate],
) -> list[AdaptiveQuestionCandidate]:
    """Rank by documented policy dimensions with stable UUID tie-breaking."""

    oldest = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(
        candidates,
        key=lambda item: (
            not item.misconception_match,
            not item.knowledge_match,
            not item.difficulty_match,
            item.last_exposure_at is not None,
            item.last_exposure_at or oldest,
            item.source,
            str(item.question_id),
        ),
    )


def _public_ordinary(question: Question) -> dict:
    return {
        "source": "ordinary",
        "id": question.id,
        "knowledge_node_id": question.knowledge_node_id,
        "difficulty_level": question.difficulty_level,
        "question_type": question.question_type,
        "question_body": question.question_body,
        "options": sanitize_public_value(question.options),
        "standard_time_seconds": question.standard_time_seconds,
        "sort_order": question.sort_order,
    }


def _public_generated(question: GeneratedQuestion) -> dict:
    return {
        "source": "generated",
        "id": question.id,
        "knowledge_node_id": question.knowledge_node_id,
        "difficulty_level": question.difficulty_level,
        "question_type": question.question_type,
        "question_body": question.question_body,
        "options": sanitize_public_value(question.options),
        "standard_time_seconds": 30,
        "sort_order": None,
    }


async def _selected_result(
    db: AsyncSession, decision: AdaptationDecision
) -> dict | None:
    if decision.selected_question_id is not None:
        question = await db.get(Question, decision.selected_question_id)
        if question is not None:
            return {"state": "ready", "question": _public_ordinary(question)}
    if decision.generated_question_id is not None:
        question = await db.get(GeneratedQuestion, decision.generated_question_id)
        if question is not None and question.quality_status == "passed":
            return {"state": "ready", "question": _public_generated(question)}
    return None


async def get_next_for_decision(
    db: AsyncSession,
    user_id: uuid.UUID,
    decision_id: uuid.UUID,
) -> dict:
    """Select once, or enqueue one recoverable variant job when no match exists."""

    decision = (
        await db.execute(
            select(AdaptationDecision)
            .where(
                AdaptationDecision.id == decision_id,
                AdaptationDecision.user_id == user_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if decision is None:
        raise LookupError("自适应决策不存在")
    selected = await _selected_result(db, decision)
    if selected is not None:
        return selected

    diagnosis = (
        await db.execute(
            select(AnswerDiagnosis).where(
                AnswerDiagnosis.id == decision.diagnosis_id,
                AnswerDiagnosis.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    target = await db.get(KnowledgeNode, decision.target_knowledge_node_id)
    if diagnosis is None or target is None:
        raise LookupError("自适应决策上下文不存在")

    excluded_ordinary: set[uuid.UUID] = set()
    excluded_generated: set[uuid.UUID] = set()
    if diagnosis.standard_answer_id is not None:
        current = await db.get(Answer, diagnosis.standard_answer_id)
        if current is not None:
            excluded_ordinary = set(
                (
                    await db.execute(
                        select(Answer.question_id).where(
                            Answer.session_id == current.session_id
                        )
                    )
                ).scalars().all()
            )
    elif diagnosis.generated_answer_id is not None:
        current = await db.get(GeneratedPracticeAnswer, diagnosis.generated_answer_id)
        if current is not None:
            excluded_generated = set(
                (
                    await db.execute(
                        select(GeneratedPracticeAnswer.generated_question_id).where(
                            GeneratedPracticeAnswer.submission_id == current.submission_id
                        )
                    )
                ).scalars().all()
            )

    ordinary_exposure = dict(
        (
            await db.execute(
                select(Answer.question_id, func.max(Answer.answered_at))
                .join(LearningSession, LearningSession.id == Answer.session_id)
                .where(LearningSession.user_id == user_id)
                .group_by(Answer.question_id)
            )
        ).all()
    )
    generated_exposure = dict(
        (
            await db.execute(
                select(
                    GeneratedPracticeAnswer.generated_question_id,
                    func.max(GeneratedPracticeAnswer.answered_at),
                )
                .join(
                    GeneratedPracticeSubmission,
                    GeneratedPracticeSubmission.id
                    == GeneratedPracticeAnswer.submission_id,
                )
                .where(GeneratedPracticeSubmission.user_id == user_id)
                .group_by(GeneratedPracticeAnswer.generated_question_id)
            )
        ).all()
    )

    ordinary = list(
        (
            await db.execute(
                select(Question).where(
                    Question.knowledge_node_id == target.id,
                    Question.question_type.in_(
                        ("CHOICE", "MULTIPLE_CHOICE", "FILL_BLANK")
                    ),
                )
            )
        ).scalars().all()
    )
    generated = list(
        (
            await db.execute(
                select(GeneratedQuestion).where(
                    GeneratedQuestion.user_id == user_id,
                    GeneratedQuestion.quality_status == "passed",
                    GeneratedQuestion.generation_status == "succeeded",
                )
            )
        ).scalars().all()
    )

    candidate_rows: dict[tuple[str, uuid.UUID], object] = {}
    candidates: list[AdaptiveQuestionCandidate] = []
    for question in ordinary:
        if question.id in excluded_ordinary or not is_question_practice_ready(question):
            continue
        candidate = AdaptiveQuestionCandidate(
            "ordinary",
            question.id,
            False,
            question.knowledge_node_id == target.id,
            question.difficulty_level == target.difficulty_level,
            ordinary_exposure.get(question.id),
        )
        candidates.append(candidate)
        candidate_rows[(candidate.source, candidate.question_id)] = question
    for question in generated:
        if question.id in excluded_generated:
            continue
        tags = (
            {str(tag) for tag in question.knowledge_tags}
            if isinstance(question.knowledge_tags, list)
            else set()
        )
        misconception_match = (
            decision.target_misconception_code is not None
            and decision.target_misconception_code in tags
        )
        knowledge_match = (
            question.knowledge_node_id == target.id or target.code in tags
        )
        if not misconception_match and not knowledge_match:
            continue
        candidate = AdaptiveQuestionCandidate(
            "generated",
            question.id,
            misconception_match,
            knowledge_match,
            question.difficulty_level == target.difficulty_level,
            generated_exposure.get(question.id),
        )
        candidates.append(candidate)
        candidate_rows[(candidate.source, candidate.question_id)] = question

    if candidates:
        chosen = rank_candidates(candidates)[0]
        row = candidate_rows[(chosen.source, chosen.question_id)]
        if chosen.source == "ordinary":
            decision.selected_question_id = chosen.question_id
            await db.flush()
            return {"state": "ready", "question": _public_ordinary(row)}
        decision.generated_question_id = chosen.question_id
        await db.flush()
        return {"state": "ready", "question": _public_generated(row)}

    if diagnosis.generated_answer_id is not None:
        source_answer = await db.get(
            GeneratedPracticeAnswer, diagnosis.generated_answer_id
        )
        if source_answer is None:
            raise LookupError("原作答不存在")
        job = await enqueue_variant_job(
            db,
            source_answer.generated_question_id,
            user_id,
            target.difficulty_level,
        )
    else:
        source_answer = await db.get(Answer, diagnosis.standard_answer_id)
        if source_answer is None:
            raise LookupError("原作答不存在")
        job = await enqueue_standard_variant_job(
            db,
            source_answer.question_id,
            user_id,
            target.difficulty_level,
        )
    return {"state": "pending_generation", "generation_job_id": job.id}
