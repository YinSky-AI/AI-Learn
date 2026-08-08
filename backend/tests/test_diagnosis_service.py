import json

import pytest

from app.domain.equation_taxonomy import (
    KnowledgePointCode,
    MisconceptionCode,
)
from app.schemas.adaptive_learning import (
    DiagnosisInput,
    DiagnosisSource,
    DiagnosisStatus,
)
from app.services.diagnosis_service import diagnose_answer


class FakeProvider:
    def __init__(self, content: str):
        self.content = content
        self.calls: list[tuple[list[dict[str, str]], dict[str, object]]] = []

    async def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return {
            "content": self.content,
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "latency_ms": 12,
        }


class RaisingProvider:
    async def generate(self, _messages, **_kwargs):
        raise TimeoutError("simulated provider timeout")


def diagnosis_input(
    *,
    steps: list[str],
    is_correct: bool = False,
    equation: str = "2(x+1)=10",
) -> DiagnosisInput:
    return DiagnosisInput(
        equation=equation,
        is_correct=is_correct,
        solution_steps=steps,
        knowledge_point_code=KnowledgePointCode.EQUATION_EQUIVALENCE,
    )


@pytest.mark.asyncio
async def test_correct_answer_needs_no_diagnosis_or_provider_call():
    """Diagnosing a server-judged correct answer must make this test fail."""

    provider = FakeProvider("{}")
    result = await diagnose_answer(
        diagnosis_input(steps=["2x+2=10", "x=4"], is_correct=True), provider
    )

    assert result.status is DiagnosisStatus.NOT_REQUIRED
    assert result.misconception_code is None
    assert result.first_invalid_transition is None
    assert provider.calls == []


@pytest.mark.asyncio
async def test_wrong_answer_without_steps_explicitly_abstains():
    """Guessing from a final answer without transitions must make this test fail."""

    provider = FakeProvider("{}")
    result = await diagnose_answer(diagnosis_input(steps=[]), provider)

    assert result.status is DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert result.first_invalid_transition is None
    assert provider.calls == []


@pytest.mark.asyncio
async def test_distribution_rule_diagnoses_without_provider():
    """Calling an LLM for a unique high-confidence expansion error must fail."""

    provider = FakeProvider("{}")
    result = await diagnose_answer(
        diagnosis_input(steps=["2(x+1)=10", "2x+1=10"]), provider
    )

    assert result.status is DiagnosisStatus.DIAGNOSED
    assert result.misconception_code is MisconceptionCode.DISTRIBUTION_ERROR
    assert result.knowledge_point_code is KnowledgePointCode.DISTRIBUTIVE_EXPANSION
    assert result.first_invalid_transition == 0
    assert result.source is DiagnosisSource.RULE
    assert result.confidence >= 0.85
    assert provider.calls == []


@pytest.mark.asyncio
async def test_sign_transfer_rule_diagnoses_without_provider():
    """Losing the deterministic term-transfer mapping must make this test fail."""

    provider = FakeProvider("{}")
    result = await diagnose_answer(
        diagnosis_input(steps=["2x+3=7", "2x=10"], equation="2x+3=7"), provider
    )

    assert result.misconception_code is MisconceptionCode.SIGN_TRANSFER_ERROR
    assert result.knowledge_point_code is KnowledgePointCode.MOVE_TERMS_SIGN
    assert provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("equation", "steps", "expected_misconception", "expected_knowledge_point"),
    [
        (
            "2x+3x=10",
            ["2x+3x=10", "4x=10"],
            MisconceptionCode.COMBINE_LIKE_TERMS_ERROR,
            KnowledgePointCode.COMBINE_LIKE_TERMS,
        ),
        (
            "2x=8",
            ["2x=8", "x=8"],
            MisconceptionCode.COEFFICIENT_NORMALIZATION_ERROR,
            KnowledgePointCode.NORMALIZE_COEFFICIENT,
        ),
        (
            "2x+2=10",
            ["2x+2=10", "2x+3=10"],
            MisconceptionCode.BALANCE_VIOLATION,
            KnowledgePointCode.EQUATION_EQUIVALENCE,
        ),
    ],
)
async def test_other_unique_rule_features_map_to_the_closed_catalog(
    equation: str,
    steps: list[str],
    expected_misconception: MisconceptionCode,
    expected_knowledge_point: KnowledgePointCode,
):
    """A wrong deterministic feature-to-taxonomy mapping must make this test fail."""

    result = await diagnose_answer(
        diagnosis_input(steps=steps, equation=equation), provider=None
    )

    assert result.misconception_code is expected_misconception
    assert result.knowledge_point_code is expected_knowledge_point


@pytest.mark.asyncio
async def test_unparseable_steps_abstain_without_provider():
    """Treating unsafe text as evidence or sending it for guessing must fail."""

    provider = FakeProvider("{}")
    result = await diagnose_answer(
        diagnosis_input(steps=["2(x+1)=10", "x.__class__=4"]), provider
    )

    assert result.status is DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert result.first_invalid_transition is None
    assert provider.calls == []


@pytest.mark.asyncio
async def test_ambiguous_rules_abstain_when_no_provider_is_available():
    """Choosing arbitrarily among conflicting rule features must make this fail."""

    result = await diagnose_answer(
        diagnosis_input(steps=["2(x+1)=10", "x+1=10"]), provider=None
    )

    assert result.status is DiagnosisStatus.INSUFFICIENT_EVIDENCE


def llm_output(**overrides: object) -> str:
    payload: dict[str, object] = {
        "misconception_code": "distribution_error",
        "knowledge_point_code": "distributive_expansion",
        "first_invalid_transition": 0,
        "evidence": "x+1=10",
        "confidence": 0.88,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        llm_output(misconception_code="invented_error"),
        llm_output(first_invalid_transition=5),
        llm_output(evidence="学生先把答案写成了 x=100"),
        "not-json",
    ],
)
async def test_invalid_or_hallucinated_provider_output_safely_abstains(content: str):
    """Persisting an invalid model enum or fabricated evidence must make this fail."""

    result = await diagnose_answer(
        diagnosis_input(steps=["2(x+1)=10", "x+1=10"]), FakeProvider(content)
    )

    assert result.status is DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert result.misconception_code is None
    assert result.first_invalid_transition is None


@pytest.mark.asyncio
async def test_valid_provider_classification_is_cross_checked_and_structured():
    """Skipping Provider options or evidence cross-checking must make this test fail."""

    provider = FakeProvider(llm_output())
    result = await diagnose_answer(
        diagnosis_input(steps=["2(x+1)=10", "x+1=10"]), provider
    )

    assert result.status is DiagnosisStatus.DIAGNOSED
    assert result.source is DiagnosisSource.HYBRID
    assert result.first_invalid_transition == 0
    assert result.model_name == "test-model"
    assert result.prompt_version is not None
    assert len(provider.calls) == 1
    _, kwargs = provider.calls[0]
    assert kwargs == {
        "max_tokens": 420,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }


@pytest.mark.asyncio
async def test_provider_failure_degrades_to_insufficient_evidence():
    """Leaking a Provider failure instead of abstaining must make this test fail."""

    result = await diagnose_answer(
        diagnosis_input(steps=["2(x+1)=10", "x+1=10"]), RaisingProvider()
    )

    assert result.status is DiagnosisStatus.INSUFFICIENT_EVIDENCE
    assert result.model_name is None
