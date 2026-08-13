"""Owner-scoped adaptive diagnosis and next-question endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.models.adaptive_learning import (
    AdaptationDecision,
    AnswerDiagnosis,
    DiagnosisJob,
)
from app.schemas.common import ApiResponse, success_response
from app.schemas.adaptive_learning import AdaptiveNextResponse, DiagnosisJobResponse


router = APIRouter()
_FAILED_MESSAGE = "诊断暂时未完成，请稍后重新作答"


def _answer_filter(model, job: DiagnosisJob):
    if job.standard_answer_id is not None:
        return model.standard_answer_id == job.standard_answer_id
    return model.generated_answer_id == job.generated_answer_id


def _safe_probability(value) -> float | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if parsed < 0 or parsed > 1:
        return None
    return float(parsed)


@router.get(
    "/diagnoses/jobs/{job_id}",
    response_model=ApiResponse[DiagnosisJobResponse],
    response_model_exclude_none=True,
)
async def get_diagnosis_job(
    job_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    job = (
        await db.execute(
            select(DiagnosisJob).where(
                DiagnosisJob.id == job_id,
                DiagnosisJob.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="诊断任务不存在",
        )
    if job.status in {"queued", "running"}:
        return success_response(
            data={"job_id": job.id, "state": "pending"},
            message="诊断处理中",
        )
    if job.status == "failed":
        return success_response(
            data={
                "job_id": job.id,
                "state": "failed",
                "retryable": False,
                "message": _FAILED_MESSAGE,
            },
            message=_FAILED_MESSAGE,
        )

    diagnosis = (
        await db.execute(
            select(AnswerDiagnosis).where(_answer_filter(AnswerDiagnosis, job))
        )
    ).scalar_one_or_none()
    if diagnosis is None:
        return success_response(
            data={
                "job_id": job.id,
                "state": "failed",
                "retryable": False,
                "message": _FAILED_MESSAGE,
            },
            message=_FAILED_MESSAGE,
        )
    decision = (
        await db.execute(
            select(AdaptationDecision).where(
                AdaptationDecision.diagnosis_id == diagnosis.id,
                AdaptationDecision.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    snapshot = diagnosis.input_snapshot if isinstance(diagnosis.input_snapshot, dict) else {}
    mastery = {
        "before": _safe_probability(snapshot.get("mastery_before")),
        "after": _safe_probability(snapshot.get("mastery_after")),
        "model_version": snapshot.get("mastery_model_version"),
    }
    next_action = None
    if decision is not None:
        reasons = decision.reason_codes if isinstance(decision.reason_codes, list) else []
        next_action = {
            "decision_id": decision.id,
            "action": decision.action,
            "reason_codes": [
                str(reason)[:64]
                for reason in reasons[:5]
                if isinstance(reason, str)
            ],
        }
    return success_response(
        data={
            "job_id": job.id,
            "state": "succeeded",
            "diagnosis": {
                "status": diagnosis.status,
                "knowledge_point_code": diagnosis.knowledge_point_code,
                "misconception_code": diagnosis.misconception_code,
                "first_invalid_step": (
                    diagnosis.first_invalid_transition + 2
                    if diagnosis.first_invalid_transition is not None
                    else None
                ),
                "evidence": diagnosis.evidence,
                "confidence": float(diagnosis.confidence),
            },
            "mastery": mastery,
            "next_action": next_action,
        },
        message="诊断完成",
    )


@router.get(
    "/next",
    response_model=ApiResponse[AdaptiveNextResponse],
    response_model_exclude_none=True,
)
async def get_next_question(
    decision_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from app.services.adaptive_question_service import get_next_for_decision

    try:
        result = await get_next_for_decision(db, user_id, decision_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_response(data=result, message="获取下一题成功")
