"""Strict contracts for the versioned equation-diagnosis dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.equation_taxonomy import KnowledgePointCode, MisconceptionCode
from app.schemas.adaptive_learning import DiagnosisStatus
from app.services.adaptive_policy import AdaptationAction


DATASET_VERSION = "equation-diagnosis-eval-v2"


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    dataset_version: Literal[DATASET_VERSION]
    category: Literal[
        "diagnostic_error",
        "valid_alternative",
        "insufficient_evidence",
        "safety",
    ]
    question: str = Field(min_length=1, max_length=1000)
    equation: str = Field(min_length=1, max_length=1000)
    final_answer: str = Field(min_length=1, max_length=1000)
    solution_steps: list[str] = Field(default_factory=list, max_length=12)
    is_correct: bool
    knowledge_point_code: KnowledgePointCode
    expected_status: DiagnosisStatus
    expected_misconception: MisconceptionCode | None = None
    expected_invalid_transition: int | None = Field(default=None, ge=0, le=11)
    acceptable_next_actions: list[AdaptationAction] = Field(min_length=1, max_length=5)
    split: Literal["development", "locked"]
    reviewed_by_second_person: bool

    @model_validator(mode="after")
    def validate_expected_result(self) -> "EvalCase":
        if self.expected_status is DiagnosisStatus.DIAGNOSED:
            if self.expected_misconception is None or self.expected_invalid_transition is None:
                raise ValueError("诊断样本必须标注错因和第一处无效转换")
        elif self.expected_misconception is not None or self.expected_invalid_transition is not None:
            raise ValueError("非诊断样本不得标注具体错因或无效转换")
        if self.reviewed_by_second_person and self.split != "locked":
            raise ValueError("二人复核标记只用于锁定测试集")
        return self


def load_cases(path: Path) -> list[EvalCase]:
    """Load JSONL strictly and reject blank records or duplicate identifiers."""

    cases: list[EvalCase] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as source:
        for line_number, raw_line in enumerate(source, start=1):
            if not raw_line.strip():
                raise ValueError(f"第 {line_number} 行为空")
            try:
                case = EvalCase.model_validate(json.loads(raw_line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {line_number} 行不是有效 JSON") from exc
            if case.id in seen:
                raise ValueError(f"评测样本 ID 重复：{case.id}")
            seen.add(case.id)
            cases.append(case)
    return cases
