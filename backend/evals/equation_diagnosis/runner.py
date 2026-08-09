"""CLI runner for offline rules and explicitly enabled Provider benchmarks."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.ai.prompts.error_diagnosis import ERROR_DIAGNOSIS_PROMPT_VERSION
from app.domain.equation_taxonomy import KnowledgePointCode, MisconceptionCode, RULE_VERSION
from app.schemas.adaptive_learning import DiagnosisInput, DiagnosisStatus, bounded_token_usage
from app.services.diagnosis_service import diagnose_answer

from .metrics import EvalPrediction, compute_metrics
from .schema import DATASET_VERSION, EvalCase, load_cases


RunnerMode = Literal["rules", "direct-llm", "structured-llm", "hybrid"]
MODEL_MODES = frozenset({"direct-llm", "structured-llm", "hybrid"})
PROMPT_VERSIONS = {
    "direct-llm": "equation-eval-direct-v1",
    "structured-llm": "equation-eval-structured-v1",
    "hybrid": ERROR_DIAGNOSIS_PROMPT_VERSION,
}
DEFAULT_CASES_PATH = Path(__file__).with_name("cases.jsonl")
ROOT = Path(__file__).resolve().parents[3]


class ProviderRunNotAllowed(RuntimeError):
    """Raised before any paid Provider can be called implicitly."""


class ModelEvalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DiagnosisStatus
    misconception_code: MisconceptionCode | None = None
    knowledge_point_code: KnowledgePointCode
    first_invalid_transition: int | None = Field(default=None, ge=0, le=11)
    evidence: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_status(self) -> "ModelEvalOutput":
        if self.status is DiagnosisStatus.DIAGNOSED:
            if self.misconception_code is None or self.first_invalid_transition is None:
                raise ValueError("diagnosed 输出必须包含错因和错误步骤")
        elif self.misconception_code is not None or self.first_invalid_transition is not None:
            raise ValueError("非 diagnosed 输出不得包含具体错因或错误步骤")
        return self


def ensure_provider_run_allowed(
    mode: str,
    *,
    allow_provider: bool,
    api_key: str,
) -> None:
    if mode not in MODEL_MODES:
        return
    if not allow_provider:
        raise ProviderRunNotAllowed("模型评测必须显式传入 --allow-provider")
    if not api_key.strip():
        raise ProviderRunNotAllowed("模型评测需要已配置的 Provider API Key")


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _input_for(case: EvalCase) -> DiagnosisInput:
    return DiagnosisInput(
        equation=case.equation,
        is_correct=case.is_correct,
        solution_steps=case.solution_steps,
        knowledge_point_code=case.knowledge_point_code,
    )


def _evidence_is_grounded(case: EvalCase, evidence: str) -> bool:
    candidates = [case.equation, *case.solution_steps]
    return any(candidate and candidate in evidence for candidate in candidates)


async def _production_prediction(case: EvalCase, provider) -> EvalPrediction:
    try:
        diagnosis_input = _input_for(case)
    except ValidationError:
        return EvalPrediction(
            case.id,
            DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            None,
            None,
            True,
            0.0,
        )
    started = perf_counter()
    result = await diagnose_answer(diagnosis_input, provider)
    latency_ms = 0.0 if provider is None else (perf_counter() - started) * 1000
    return EvalPrediction(
        case_id=case.id,
        predicted_status=result.status,
        predicted_misconception=(
            result.misconception_code.value if result.misconception_code else None
        ),
        predicted_invalid_transition=result.first_invalid_transition,
        evidence_valid=(
            result.status is not DiagnosisStatus.DIAGNOSED
            or _evidence_is_grounded(case, result.evidence)
        ),
        latency_ms=latency_ms,
        token_usage=result.token_usage or {},
    )


def _model_prompt(case: EvalCase) -> list[dict[str, str]]:
    payload = {
        "equation": case.equation,
        "final_answer": case.final_answer,
        "solution_steps": case.solution_steps,
        "is_correct": case.is_correct,
        "knowledge_point_code": case.knowledge_point_code.value,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是方程错因分类器。只返回 JSON；不得补写学生未提供的步骤。"
                "status 只能为 diagnosed、insufficient_evidence、not_required。"
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


async def _provider_only_prediction(
    case: EvalCase,
    provider,
    *,
    structured: bool,
) -> EvalPrediction:
    started = perf_counter()
    kwargs: dict[str, object] = {"max_tokens": 420, "temperature": 0.1}
    if structured:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        response = await provider.generate(_model_prompt(case), **kwargs)
        output = ModelEvalOutput.model_validate_json(response.get("content", ""))
        evidence_valid = (
            output.status is not DiagnosisStatus.DIAGNOSED
            or _evidence_is_grounded(case, output.evidence)
        )
        return EvalPrediction(
            case.id,
            output.status,
            output.misconception_code.value if output.misconception_code else None,
            output.first_invalid_transition,
            evidence_valid,
            (perf_counter() - started) * 1000,
            invalid_output=not evidence_valid,
            token_usage=bounded_token_usage(response.get("usage")) or {},
        )
    except Exception:
        return EvalPrediction(
            case.id,
            DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            None,
            None,
            True,
            (perf_counter() - started) * 1000,
            invalid_output=True,
        )


async def evaluate(
    cases: list[EvalCase],
    mode: RunnerMode,
    provider=None,
) -> tuple[list[EvalPrediction], dict[str, object]]:
    if mode == "rules":
        predictions = [await _production_prediction(case, None) for case in cases]
    elif mode == "hybrid":
        predictions = [await _production_prediction(case, provider) for case in cases]
    else:
        predictions = [
            await _provider_only_prediction(
                case,
                provider,
                structured=mode == "structured-llm",
            )
            for case in cases
        ]

    locked = [case for case in cases if case.split == "locked"]
    reviewed_locked = [case for case in locked if case.reviewed_by_second_person]
    report: dict[str, object] = {
        "dataset_version": DATASET_VERSION,
        "git_commit": _git_commit(),
        "mode": mode,
        "model_name": getattr(provider, "model", None) if provider is not None else None,
        "prompt_version": PROMPT_VERSIONS.get(mode),
        "rule_version": RULE_VERSION,
        "case_count": len(cases),
        "split_counts": {
            "development": sum(case.split == "development" for case in cases),
            "locked": len(locked),
            "locked_reviewed": len(reviewed_locked),
        },
        "metrics": compute_metrics(cases, predictions),
        "prediction_counts": {
            status.value: sum(
                prediction.predicted_status == status for prediction in predictions
            )
            for status in DiagnosisStatus
        },
        "failure_counts": {
            "invalid_output": sum(
                prediction.invalid_output for prediction in predictions
            ),
            "ungrounded_evidence": sum(
                not prediction.evidence_valid for prediction in predictions
            ),
        },
        "predictions": [asdict(prediction) for prediction in predictions],
        "resume_metrics": {
            "eligible": bool(locked) and len(reviewed_locked) == len(locked),
            "reason": (
                None
                if locked and len(reviewed_locked) == len(locked)
                else "locked split 尚未完成独立二人复核"
            ),
            "metrics": (
                compute_metrics(
                    reviewed_locked,
                    [prediction for prediction in predictions if prediction.case_id in {case.id for case in reviewed_locked}],
                )
                if locked and len(reviewed_locked) == len(locked)
                else None
            ),
        },
    }
    return predictions, report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行一元一次方程诊断离线评测")
    parser.add_argument(
        "--mode",
        choices=("rules", "direct-llm", "structured-llm", "hybrid"),
        required=True,
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-provider", action="store_true")
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    cases = load_cases(args.cases)
    provider = None
    if args.mode in MODEL_MODES:
        from app.core.config import settings

        try:
            ensure_provider_run_allowed(
                args.mode,
                allow_provider=args.allow_provider,
                api_key=settings.DEEPSEEK_API_KEY,
            )
        except ProviderRunNotAllowed as exc:
            parser.error(str(exc))
        if any(
            case.split == "locked" and not case.reviewed_by_second_person
            for case in cases
        ):
            parser.error("locked split 尚未完成独立二人复核")
        from app.ai.provider import get_ai_provider

        provider = get_ai_provider()
    _, report = asyncio.run(evaluate(cases, args.mode, provider))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"评测完成：mode={args.mode} cases={len(cases)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
