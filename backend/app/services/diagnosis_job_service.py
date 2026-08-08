"""Durable diagnosis queue with Provider work outside database transactions."""

from __future__ import annotations

import uuid
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.equation_taxonomy import KnowledgePointCode
from app.models.adaptive_learning import (
    AdaptationDecision,
    AnswerDiagnosis,
    DiagnosisJob,
)
from app.models.content import KnowledgeNode
from app.schemas.adaptive_learning import DiagnosisInput, ErrorDiagnosisResult
from app.services.adaptive_policy import AdaptiveContext, decide_next_action
from app.services.diagnosis_service import diagnose_answer
from app.services.mastery_service import update_mastery_once


_MAX_INPUT_SNAPSHOT_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class DiagnosisAnswerReference:
    standard_answer_id: uuid.UUID | None = None
    generated_answer_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if (self.standard_answer_id is None) == (self.generated_answer_id is None):
            raise ValueError("必须恰好一个答案 ID")


@dataclass(frozen=True, slots=True)
class ClaimedDiagnosisJob:
    job_id: uuid.UUID
    user_id: uuid.UUID
    standard_answer_id: uuid.UUID | None
    generated_answer_id: uuid.UUID | None
    attempts: int
    max_attempts: int
    lease_owner: str
    input_snapshot: dict[str, Any]

    @property
    def answer_reference(self) -> str:
        if self.standard_answer_id is not None:
            return f"answer:{self.standard_answer_id}"
        return f"generated_answer:{self.generated_answer_id}"


def _answer_filter(model, reference: DiagnosisAnswerReference):
    if reference.standard_answer_id is not None:
        return model.standard_answer_id == reference.standard_answer_id
    return model.generated_answer_id == reference.generated_answer_id


async def enqueue_diagnosis_job(
    db: AsyncSession,
    answer_reference: DiagnosisAnswerReference,
    user_id: uuid.UUID,
    *,
    input_snapshot: dict[str, Any],
) -> DiagnosisJob:
    encoded_snapshot = json.dumps(
        input_snapshot, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded_snapshot) > _MAX_INPUT_SNAPSHOT_BYTES:
        raise ValueError("诊断输入快照过大")
    existing = (
        await db.execute(
            select(DiagnosisJob).where(_answer_filter(DiagnosisJob, answer_reference))
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    job = DiagnosisJob(
        user_id=user_id,
        standard_answer_id=answer_reference.standard_answer_id,
        generated_answer_id=answer_reference.generated_answer_id,
        status="queued",
        input_snapshot=dict(input_snapshot),
    )
    db.add(job)
    await db.flush()
    return job


async def claim_diagnosis_job(
    db: AsyncSession,
    worker_id: str,
    lease_seconds: int = 120,
) -> ClaimedDiagnosisJob | None:
    now = datetime.now(timezone.utc)
    row = (
        await db.execute(
            select(DiagnosisJob)
            .where(
                DiagnosisJob.attempts < DiagnosisJob.max_attempts,
                or_(
                    DiagnosisJob.status == "queued",
                    (DiagnosisJob.status == "running")
                    & (DiagnosisJob.lease_expires_at < now),
                ),
            )
            .order_by(DiagnosisJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.status = "running"
    row.attempts += 1
    row.lease_owner = worker_id
    row.lease_expires_at = now + timedelta(seconds=lease_seconds)
    row.failure_reason = None
    await db.flush()
    return ClaimedDiagnosisJob(
        job_id=row.id,
        user_id=row.user_id,
        standard_answer_id=row.standard_answer_id,
        generated_answer_id=row.generated_answer_id,
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        lease_owner=worker_id,
        input_snapshot=dict(row.input_snapshot),
    )


async def _mark_retry_or_failed(session_factory, claimed: ClaimedDiagnosisJob, reason: str) -> None:
    async with session_factory() as db:
        async with db.begin():
            row = (
                await db.execute(
                    select(DiagnosisJob)
                    .where(DiagnosisJob.id == claimed.job_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None or row.status != "running" or row.lease_owner != claimed.lease_owner:
                return
            row.status = "failed" if row.attempts >= row.max_attempts else "queued"
            row.failure_reason = reason[:100]
            row.lease_owner = None
            row.lease_expires_at = None


async def persist_diagnosis_result(
    session_factory,
    claimed: ClaimedDiagnosisJob,
    result: ErrorDiagnosisResult,
) -> None:
    reference = DiagnosisAnswerReference(
        standard_answer_id=claimed.standard_answer_id,
        generated_answer_id=claimed.generated_answer_id,
    )
    async with session_factory() as db:
        async with db.begin():
            job = (
                await db.execute(
                    select(DiagnosisJob)
                    .where(DiagnosisJob.id == claimed.job_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if job is None or job.status != "running" or job.lease_owner != claimed.lease_owner:
                return
            existing = (
                await db.execute(
                    select(AnswerDiagnosis).where(
                        _answer_filter(AnswerDiagnosis, reference)
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                job.status = "succeeded"
                job.lease_owner = None
                job.lease_expires_at = None
                return

            diagnosis = AnswerDiagnosis(
                user_id=claimed.user_id,
                standard_answer_id=claimed.standard_answer_id,
                generated_answer_id=claimed.generated_answer_id,
                status=result.status.value,
                knowledge_point_code=result.knowledge_point_code.value,
                misconception_code=(result.misconception_code.value if result.misconception_code else None),
                first_invalid_transition=result.first_invalid_transition,
                evidence=result.evidence,
                confidence=result.confidence,
                source=result.source.value,
                input_snapshot=dict(claimed.input_snapshot),
                prompt_version=result.prompt_version,
                model_name=result.model_name,
                latency_ms=result.latency_ms,
                token_usage=result.token_usage,
            )
            db.add(diagnosis)
            await db.flush()

            mastery = await update_mastery_once(
                db,
                diagnosis,
                correct=bool(claimed.input_snapshot["is_correct"]),
            )
            prerequisite_code = None
            prerequisites = mastery.knowledge_node.prerequisites or []
            if prerequisites:
                prerequisite = (
                    await db.execute(
                        select(KnowledgeNode).where(KnowledgeNode.id == prerequisites[0])
                    )
                ).scalar_one_or_none()
                if prerequisite is not None:
                    try:
                        prerequisite_code = KnowledgePointCode(prerequisite.code)
                    except ValueError:
                        prerequisite_code = None

            decision_data = decide_next_action(
                AdaptiveContext(
                    diagnosis_status=result.status,
                    knowledge_point_code=result.knowledge_point_code,
                    misconception_code=result.misconception_code,
                    p_known=mastery.after,
                    prerequisite_knowledge_point_code=prerequisite_code,
                    recent_correctness=(bool(claimed.input_snapshot["is_correct"]),),
                    recent_misconceptions=(
                        (result.misconception_code,) if result.misconception_code else ()
                    ),
                )
            )
            target = (
                await db.execute(
                    select(KnowledgeNode).where(
                        KnowledgeNode.code == decision_data.target_knowledge_point_code.value
                    )
                )
            ).scalar_one()
            db.add(
                AdaptationDecision(
                    user_id=claimed.user_id,
                    diagnosis_id=diagnosis.id,
                    action=decision_data.action.value,
                    target_knowledge_node_id=target.id,
                    target_misconception_code=(
                        decision_data.target_misconception_code.value
                        if decision_data.target_misconception_code
                        else None
                    ),
                    reason_codes=list(decision_data.reason_codes),
                    policy_version=decision_data.policy_version,
                )
            )
            job.status = "succeeded"
            job.lease_owner = None
            job.lease_expires_at = None


async def process_diagnosis_job(
    session_factory,
    claimed: ClaimedDiagnosisJob,
    provider,
) -> None:
    """Validate and diagnose without a session, then persist in a short transaction."""

    try:
        diagnosis_input = DiagnosisInput.model_validate(claimed.input_snapshot)
        result = await diagnose_answer(diagnosis_input, provider)
        await persist_diagnosis_result(session_factory, claimed, result)
    except Exception:
        await _mark_retry_or_failed(session_factory, claimed, "diagnosis_processing_failed")
