import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.equation_diagnosis.schema import (
    DATASET_VERSION,
    EvalCase,
    load_cases,
)
from evals.equation_diagnosis.runner import (
    ProviderRunNotAllowed,
    _model_prompt,
    ensure_provider_run_allowed,
    evaluate,
)


CASES_PATH = Path(__file__).parents[1] / "evals" / "equation_diagnosis" / "cases.jsonl"


def valid_case(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "eq-v1-001",
        "dataset_version": DATASET_VERSION,
        "category": "diagnostic_error",
        "question": "解方程 2(x+1)=10。",
        "equation": "2(x+1)=10",
        "final_answer": "x=4.5",
        "solution_steps": ["2(x+1)=10", "2x+1=10"],
        "is_correct": False,
        "knowledge_point_code": "distributive_expansion",
        "expected_status": "diagnosed",
        "expected_misconception": "distribution_error",
        "expected_invalid_transition": 0,
        "acceptable_next_actions": ["practice_misconception"],
        "split": "development",
        "reviewed_by_second_person": False,
    }
    payload.update(overrides)
    return payload


def test_eval_case_rejects_unknown_labels_and_inconsistent_expectations():
    with pytest.raises(ValidationError):
        EvalCase.model_validate(valid_case(expected_misconception="invented_error"))
    with pytest.raises(ValidationError):
        EvalCase.model_validate(
            valid_case(expected_status="insufficient_evidence", expected_invalid_transition=0)
        )


def test_loader_rejects_duplicate_ids(tmp_path: Path):
    path = tmp_path / "duplicate.jsonl"
    line = json.dumps(valid_case(), ensure_ascii=False)
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="重复"):
        load_cases(path)


def test_versioned_dataset_has_exact_locked_distribution():
    cases = load_cases(CASES_PATH)

    assert len(cases) == 160
    assert {case.dataset_version for case in cases} == {DATASET_VERSION}
    assert len({case.id for case in cases}) == 160
    assert sum(case.category == "diagnostic_error" for case in cases) == 80
    assert sum(case.category == "valid_alternative" for case in cases) == 30
    assert sum(case.category == "insufficient_evidence" for case in cases) == 30
    assert sum(case.category == "safety" for case in cases) == 20
    assert sum(case.split == "locked" for case in cases) == 40
    assert {
        category: sum(
            case.split == "locked" and case.category == category for case in cases
        )
        for category in {
            "diagnostic_error",
            "valid_alternative",
            "insufficient_evidence",
            "safety",
        }
    } == {
        "diagnostic_error": 20,
        "valid_alternative": 8,
        "insufficient_evidence": 7,
        "safety": 5,
    }
    assert all(
        not case.reviewed_by_second_person
        for case in cases
        if case.split == "development"
    )

    diagnostic_counts = {
        code: sum(case.expected_misconception == code for case in cases)
        for code in {
            "balance_violation",
            "sign_transfer_error",
            "distribution_error",
            "combine_like_terms_error",
            "coefficient_normalization_error",
            "arithmetic_slip",
        }
    }
    assert sum(diagnostic_counts.values()) == 80
    assert all(count >= 13 for count in diagnostic_counts.values())
    locked_diagnostic_counts = {
        code: sum(
            case.split == "locked" and case.expected_misconception == code
            for case in cases
        )
        for code in diagnostic_counts
    }
    assert sum(locked_diagnostic_counts.values()) == 20
    assert all(count >= 3 for count in locked_diagnostic_counts.values())


@pytest.mark.parametrize("mode", ["direct-llm", "structured-llm", "hybrid"])
def test_model_modes_fail_closed_without_explicit_permission_and_key(mode: str):
    with pytest.raises(ProviderRunNotAllowed, match="--allow-provider"):
        ensure_provider_run_allowed(mode, allow_provider=False, api_key="configured")
    with pytest.raises(ProviderRunNotAllowed, match="API Key"):
        ensure_provider_run_allowed(mode, allow_provider=True, api_key="")

    ensure_provider_run_allowed(mode, allow_provider=True, api_key="configured")


def test_rules_mode_never_requires_provider_permission():
    ensure_provider_run_allowed("rules", allow_provider=False, api_key="")


def test_model_prompt_declares_the_exact_json_output_contract():
    case = EvalCase.model_validate(valid_case())
    system_prompt = _model_prompt(case)[0]["content"]

    for field in (
        "status",
        "misconception_code",
        "knowledge_point_code",
        "first_invalid_transition",
        "evidence",
        "confidence",
    ):
        assert field in system_prompt
    assert "distribution_error" in system_prompt
    assert "insufficient_evidence" in system_prompt
    assert "null" in system_prompt


@pytest.mark.asyncio
async def test_rules_report_is_auditable_and_never_calls_provider():
    class ForbiddenProvider:
        async def generate(self, *_args, **_kwargs):
            raise AssertionError("rules mode 不得调用 Provider")

    cases = load_cases(CASES_PATH)
    predictions, report = await evaluate(cases, "rules", ForbiddenProvider())
    reviewed_locked = sum(
        case.split == "locked" and case.reviewed_by_second_person for case in cases
    )

    assert len(predictions) == 160
    assert report["model_name"] is None
    assert report["split_counts"] == {
        "development": 120,
        "locked": 40,
        "locked_reviewed": reviewed_locked,
    }
    assert report["resume_metrics"]["eligible"] is (reviewed_locked == 40)
    assert len(report["predictions"]) == 160
    assert report["failure_counts"]["invalid_output"] == 0
