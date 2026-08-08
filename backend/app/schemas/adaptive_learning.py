"""Validated contracts for diagnosis and adaptive-learning services."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.equation_taxonomy import KnowledgePointCode, MisconceptionCode
from app.services.question_access import sanitize_public_value


class DiagnosisStatus(StrEnum):
    DIAGNOSED = "diagnosed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_REQUIRED = "not_required"


class DiagnosisSource(StrEnum):
    RULE = "rule"
    HYBRID = "hybrid"
    FALLBACK = "fallback"


class DiagnosisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equation: str = Field(min_length=1, max_length=200)
    is_correct: bool
    solution_steps: list[str] = Field(default_factory=list, max_length=12)
    knowledge_point_code: KnowledgePointCode

    @field_validator("solution_steps")
    @classmethod
    def validate_step_lengths(cls, steps: list[str]) -> list[str]:
        if any(len(step) > 200 for step in steps):
            raise ValueError("每个解题步骤最多 200 个字符")
        return steps


class ErrorDiagnosisLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    misconception_code: MisconceptionCode
    knowledge_point_code: KnowledgePointCode
    first_invalid_transition: int = Field(ge=0)
    evidence: str = Field(min_length=1, max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)


class ErrorDiagnosisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DiagnosisStatus
    misconception_code: MisconceptionCode | None = None
    knowledge_point_code: KnowledgePointCode
    first_invalid_transition: int | None = None
    evidence: str = Field(max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    source: DiagnosisSource
    rule_version: str
    prompt_version: str | None = None
    model_name: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    token_usage: dict[str, int] | None = None

    @model_validator(mode="after")
    def validate_status_contract(self) -> "ErrorDiagnosisResult":
        if self.status is DiagnosisStatus.DIAGNOSED:
            if self.misconception_code is None or self.first_invalid_transition is None:
                raise ValueError("已诊断结果必须包含错因和第一处无效转换")
        elif self.misconception_code is not None or self.first_invalid_transition is not None:
            raise ValueError("非诊断结果不得伪造错因或错误步骤")
        return self


def bounded_token_usage(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    result = {
        key: int(value[key])
        for key in keys
        if isinstance(value.get(key), int) and 0 <= value[key] <= 10_000_000
    }
    return result or None


class PublicDiagnosis(BaseModel):
    status: DiagnosisStatus
    knowledge_point_code: KnowledgePointCode
    misconception_code: MisconceptionCode | None = None
    first_invalid_step: int | None = Field(default=None, ge=2)
    evidence: str = Field(max_length=500)
    confidence: float = Field(ge=0, le=1)


class PublicMasteryChange(BaseModel):
    before: float | None = Field(default=None, ge=0, le=1)
    after: float | None = Field(default=None, ge=0, le=1)
    model_version: str | None = None


class PublicNextAction(BaseModel):
    decision_id: UUID
    action: str
    reason_codes: list[str] = Field(default_factory=list, max_length=5)


class DiagnosisJobResponse(BaseModel):
    job_id: UUID
    state: Literal["pending", "succeeded", "failed"]
    retryable: bool | None = None
    message: str | None = None
    diagnosis: PublicDiagnosis | None = None
    mastery: PublicMasteryChange | None = None
    next_action: PublicNextAction | None = None


class AdaptiveQuestionPublic(BaseModel):
    source: Literal["ordinary", "generated"]
    id: UUID
    knowledge_node_id: UUID | None = None
    difficulty_level: str
    question_type: str
    question_body: str
    options: list[dict[str, Any]] | None = None
    standard_time_seconds: int
    sort_order: int | None = None

    @field_validator("options", mode="before")
    @classmethod
    def sanitize_options(cls, value):
        return sanitize_public_value(value)


class AdaptiveNextResponse(BaseModel):
    state: Literal["ready", "pending_generation"]
    question: AdaptiveQuestionPublic | None = None
    generation_job_id: UUID | None = None
