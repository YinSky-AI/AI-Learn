"""Deterministic metrics for equation-diagnosis predictions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from app.domain.equation_taxonomy import MisconceptionCode
from app.schemas.adaptive_learning import DiagnosisStatus

from .schema import EvalCase


CONCRETE_MISCONCEPTIONS = tuple(
    code.value
    for code in MisconceptionCode
    if code
    not in {
        MisconceptionCode.MULTIPLE_POSSIBLE_CAUSES,
        MisconceptionCode.INSUFFICIENT_EVIDENCE,
    }
)


@dataclass(frozen=True, slots=True)
class EvalPrediction:
    case_id: str
    predicted_status: str
    predicted_misconception: str | None
    predicted_invalid_transition: int | None
    evidence_valid: bool
    latency_ms: float
    invalid_output: bool = False
    token_usage: dict[str, int] = field(default_factory=dict)


def percentile(values: Sequence[float | int], quantile: float) -> float | None:
    """Return a deterministic linearly interpolated percentile."""

    if not values:
        return None
    if not 0 <= quantile <= 1:
        raise ValueError("quantile 必须位于 0 到 1")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def compute_metrics(
    cases: Sequence[EvalCase],
    predictions: Sequence[EvalPrediction],
) -> dict[str, Any]:
    if len(cases) != len(predictions):
        raise ValueError("样本数与预测数不一致")
    by_id = {prediction.case_id: prediction for prediction in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {case.id for case in cases}:
        raise ValueError("预测 ID 必须与评测样本一一对应")

    confusion = {
        expected: {predicted: 0 for predicted in CONCRETE_MISCONCEPTIONS}
        for expected in CONCRETE_MISCONCEPTIONS
    }
    for case in cases:
        prediction = by_id[case.id]
        expected = (
            case.expected_misconception.value
            if case.expected_misconception in set(MisconceptionCode)
            else None
        )
        predicted = prediction.predicted_misconception
        if expected in confusion and predicted in confusion[expected]:
            confusion[expected][predicted] += 1

    per_class_f1: dict[str, float] = {}
    for label in CONCRETE_MISCONCEPTIONS:
        true_positive = confusion[label][label]
        false_positive = sum(
            1
            for case in cases
            if by_id[case.id].predicted_misconception == label
            and case.expected_misconception != label
        )
        false_negative = sum(
            1
            for case in cases
            if case.expected_misconception == label
            and by_id[case.id].predicted_misconception != label
        )
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        per_class_f1[label] = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

    step_cases = [case for case in cases if case.expected_invalid_transition is not None]
    correct_steps = sum(
        by_id[case.id].predicted_status == DiagnosisStatus.DIAGNOSED
        and by_id[case.id].predicted_invalid_transition == case.expected_invalid_transition
        for case in step_cases
    )
    abstention_cases = [
        case
        for case in cases
        if case.expected_status is DiagnosisStatus.INSUFFICIENT_EVIDENCE
    ]
    correct_abstentions = sum(
        by_id[case.id].predicted_status == DiagnosisStatus.INSUFFICIENT_EVIDENCE
        for case in abstention_cases
    )
    diagnosed_predictions = [
        prediction
        for prediction in predictions
        if prediction.predicted_status == DiagnosisStatus.DIAGNOSED
    ]
    hallucinated = sum(not prediction.evidence_valid for prediction in diagnosed_predictions)

    token_distribution: dict[str, dict[str, float | None] | int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        values = [
            prediction.token_usage[key]
            for prediction in predictions
            if key in prediction.token_usage
        ]
        token_distribution[key] = {
            "total": sum(values),
            "p50": percentile(values, 0.50),
            "p95": percentile(values, 0.95),
        }

    return {
        "case_count": len(cases),
        "confusion_matrix": confusion,
        "per_class_f1": per_class_f1,
        "macro_f1": sum(per_class_f1.values()) / len(CONCRETE_MISCONCEPTIONS),
        "first_invalid_step_accuracy": _ratio(correct_steps, len(step_cases)),
        "abstention_recall": _ratio(correct_abstentions, len(abstention_cases)),
        "hallucinated_evidence_rate": _ratio(hallucinated, len(diagnosed_predictions)),
        "invalid_output_rate": _ratio(
            sum(prediction.invalid_output for prediction in predictions), len(predictions)
        ),
        "latency_ms": {
            "p50": percentile([prediction.latency_ms for prediction in predictions], 0.50),
            "p95": percentile([prediction.latency_ms for prediction in predictions], 0.95),
        },
        "token_usage": token_distribution,
    }
