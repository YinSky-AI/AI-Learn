import pytest

from evals.equation_diagnosis.metrics import EvalPrediction, compute_metrics, percentile
from evals.equation_diagnosis.schema import EvalCase


def make_case(
    case_id: str,
    *,
    status: str,
    misconception: str | None = None,
    transition: int | None = None,
) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": case_id,
            "dataset_version": "equation-diagnosis-eval-v1",
            "category": "diagnostic_error" if status == "diagnosed" else "insufficient_evidence",
            "question": "解方程 2x+2=10。",
            "equation": "2x+2=10",
            "final_answer": "x=5",
            "solution_steps": ["2x+2=10", "2x=8"],
            "is_correct": status == "not_required",
            "knowledge_point_code": "equation_equivalence",
            "expected_status": status,
            "expected_misconception": misconception,
            "expected_invalid_transition": transition,
            "acceptable_next_actions": [
                "practice_misconception" if status == "diagnosed" else "ask_diagnostic_question"
            ],
            "split": "development",
            "reviewed_by_second_person": False,
        }
    )


def test_six_case_metrics_match_hand_calculation():
    cases = [
        make_case("c1", status="diagnosed", misconception="distribution_error", transition=0),
        make_case("c2", status="diagnosed", misconception="sign_transfer_error", transition=1),
        make_case("c3", status="diagnosed", misconception="arithmetic_slip", transition=0),
        make_case("c4", status="insufficient_evidence"),
        make_case("c5", status="insufficient_evidence"),
        make_case("c6", status="not_required"),
    ]
    predictions = [
        EvalPrediction("c1", "diagnosed", "distribution_error", 0, True, 10),
        EvalPrediction("c2", "diagnosed", "distribution_error", 0, True, 20),
        EvalPrediction("c3", "insufficient_evidence", None, None, True, 30, invalid_output=True),
        EvalPrediction("c4", "insufficient_evidence", None, None, True, 40),
        EvalPrediction("c5", "diagnosed", "balance_violation", 0, False, 50),
        EvalPrediction("c6", "not_required", None, None, True, 60),
    ]

    metrics = compute_metrics(cases, predictions)

    assert metrics["confusion_matrix"]["distribution_error"]["distribution_error"] == 1
    assert metrics["per_class_f1"]["distribution_error"] == pytest.approx(2 / 3)
    assert metrics["macro_f1"] == pytest.approx((2 / 3) / 6)
    assert metrics["first_invalid_step_accuracy"] == pytest.approx(1 / 3)
    assert metrics["abstention_recall"] == pytest.approx(1 / 2)
    assert metrics["hallucinated_evidence_rate"] == pytest.approx(1 / 3)
    assert metrics["invalid_output_rate"] == pytest.approx(1 / 6)
    assert metrics["latency_ms"] == {"p50": 35.0, "p95": 57.5}


def test_percentile_uses_linear_interpolation_and_handles_empty_input():
    assert percentile([], 0.5) is None
    assert percentile([10, 20, 30, 40], 0.5) == 25.0
    assert percentile([10, 20, 30, 40], 0.95) == pytest.approx(38.5)
