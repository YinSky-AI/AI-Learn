"""Evidence-first equation diagnosis with a constrained Provider fallback."""

from __future__ import annotations

from dataclasses import dataclass
from app.ai.prompts.error_diagnosis import (
    ERROR_DIAGNOSIS_PROMPT_VERSION,
    build_error_diagnosis_prompt,
)
from app.ai.tutor.agents import TutorProvider
from app.data.equation_misconceptions import MISCONCEPTION_DEFINITIONS
from app.domain.equation_parser import EquationSyntaxError, equations_are_equivalent, parse_linear_equation
from app.domain.equation_taxonomy import (
    KnowledgePointCode,
    MisconceptionCode,
    RULE_CONFIDENCE_THRESHOLD,
    RULE_VERSION,
)
from app.domain.equation_verifier import StepVerification, TransitionFeature, verify_solution_steps
from app.schemas.adaptive_learning import (
    DiagnosisInput,
    DiagnosisSource,
    DiagnosisStatus,
    ErrorDiagnosisLLMOutput,
    ErrorDiagnosisResult,
    bounded_token_usage,
)


@dataclass(frozen=True)
class _RuleCandidate:
    misconception_code: MisconceptionCode
    knowledge_point_code: KnowledgePointCode
    confidence: float


def _abstain(
    knowledge_point: KnowledgePointCode,
    evidence: str,
    *,
    prompt_version: str | None = None,
    model_name: str | None = None,
    latency_ms: int | None = None,
    token_usage: dict[str, int] | None = None,
) -> ErrorDiagnosisResult:
    return ErrorDiagnosisResult(
        status=DiagnosisStatus.INSUFFICIENT_EVIDENCE,
        knowledge_point_code=knowledge_point,
        evidence=evidence,
        confidence=0.0,
        source=DiagnosisSource.FALLBACK,
        rule_version=RULE_VERSION,
        prompt_version=prompt_version,
        model_name=model_name,
        latency_ms=latency_ms,
        token_usage=token_usage,
    )


def _provider_abstain(
    knowledge_point: KnowledgePointCode,
    evidence: str,
    response: dict[str, object],
) -> ErrorDiagnosisResult:
    return _abstain(
        knowledge_point,
        evidence,
        prompt_version=ERROR_DIAGNOSIS_PROMPT_VERSION,
        model_name=str(response.get("model")) if response.get("model") else None,
        latency_ms=(
            response.get("latency_ms")
            if isinstance(response.get("latency_ms"), int)
            else None
        ),
        token_usage=bounded_token_usage(response.get("usage")),
    )


def _evidence_steps(diagnosis_input: DiagnosisInput) -> list[str]:
    steps = list(diagnosis_input.solution_steps)
    if not steps:
        return []
    try:
        equation = parse_linear_equation(diagnosis_input.equation)
        first_step = parse_linear_equation(steps[0])
    except EquationSyntaxError:
        return steps
    if equations_are_equivalent(equation, first_step):
        return steps
    return [diagnosis_input.equation, *steps]


def _rule_candidates(verification: StepVerification) -> list[_RuleCandidate]:
    features = verification.features
    candidates: list[_RuleCandidate] = []
    mappings = (
        (
            TransitionFeature.DISTRIBUTION_ATTEMPT,
            MisconceptionCode.DISTRIBUTION_ERROR,
            KnowledgePointCode.DISTRIBUTIVE_EXPANSION,
            0.95,
        ),
        (
            TransitionFeature.COMBINE_LIKE_TERMS_ATTEMPT,
            MisconceptionCode.COMBINE_LIKE_TERMS_ERROR,
            KnowledgePointCode.COMBINE_LIKE_TERMS,
            0.92,
        ),
        (
            TransitionFeature.COEFFICIENT_NORMALIZATION_ATTEMPT,
            MisconceptionCode.COEFFICIENT_NORMALIZATION_ERROR,
            KnowledgePointCode.NORMALIZE_COEFFICIENT,
            0.94,
        ),
        (
            TransitionFeature.MOVE_TERMS_ATTEMPT,
            MisconceptionCode.SIGN_TRANSFER_ERROR,
            KnowledgePointCode.MOVE_TERMS_SIGN,
            0.90,
        ),
    )
    for feature, misconception, knowledge_point, confidence in mappings:
        if feature in features:
            candidates.append(_RuleCandidate(misconception, knowledge_point, confidence))
    if not candidates and TransitionFeature.ONE_SIDE_CHANGED in features:
        candidates.append(
            _RuleCandidate(
                MisconceptionCode.BALANCE_VIOLATION,
                KnowledgePointCode.EQUATION_EQUIVALENCE,
                0.90,
            )
        )
    return candidates


def _verified_evidence(steps: list[str], transition: int) -> str:
    return f"从步骤 {transition + 1} 到步骤 {transition + 2} 不等价：{steps[transition]} → {steps[transition + 1]}"


def _diagnosed_from_rule(
    candidate: _RuleCandidate,
    verification: StepVerification,
    steps: list[str],
) -> ErrorDiagnosisResult:
    assert verification.first_invalid_transition is not None
    return ErrorDiagnosisResult(
        status=DiagnosisStatus.DIAGNOSED,
        misconception_code=candidate.misconception_code,
        knowledge_point_code=candidate.knowledge_point_code,
        first_invalid_transition=verification.first_invalid_transition,
        evidence=_verified_evidence(steps, verification.first_invalid_transition),
        confidence=candidate.confidence,
        source=DiagnosisSource.RULE,
        rule_version=RULE_VERSION,
    )


async def _diagnose_with_provider(
    diagnosis_input: DiagnosisInput,
    provider: TutorProvider,
    verification: StepVerification,
    steps: list[str],
) -> ErrorDiagnosisResult:
    assert verification.first_invalid_transition is not None
    try:
        response = await provider.generate(
            build_error_diagnosis_prompt(diagnosis_input, verification),
            max_tokens=420,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception:
        return _abstain(diagnosis_input.knowledge_point_code, "模型归类不可用，当前证据不足")
    try:
        output = ErrorDiagnosisLLMOutput.model_validate_json(response.get("content", ""))
    except Exception:
        return _provider_abstain(
            diagnosis_input.knowledge_point_code,
            "模型归类不可用，当前证据不足",
            response,
        )

    transition = verification.first_invalid_transition
    concrete_codes = {
        code
        for code in MisconceptionCode
        if code
        not in {
            MisconceptionCode.MULTIPLE_POSSIBLE_CAUSES,
            MisconceptionCode.INSUFFICIENT_EVIDENCE,
        }
    }
    if (
        output.misconception_code not in concrete_codes
        or output.first_invalid_transition != transition
        or output.evidence not in {steps[transition], steps[transition + 1]}
        or output.confidence < 0.60
    ):
        return _provider_abstain(
            diagnosis_input.knowledge_point_code,
            "模型证据未通过校验，当前证据不足",
            response,
        )
    definition = MISCONCEPTION_DEFINITIONS[output.misconception_code]
    if output.knowledge_point_code is not definition.knowledge_point_code:
        return _provider_abstain(
            diagnosis_input.knowledge_point_code,
            "模型知识点未通过校验，当前证据不足",
            response,
        )
    return ErrorDiagnosisResult(
        status=DiagnosisStatus.DIAGNOSED,
        misconception_code=output.misconception_code,
        knowledge_point_code=output.knowledge_point_code,
        first_invalid_transition=transition,
        evidence=_verified_evidence(steps, transition),
        confidence=output.confidence,
        source=DiagnosisSource.HYBRID,
        rule_version=RULE_VERSION,
        prompt_version=ERROR_DIAGNOSIS_PROMPT_VERSION,
        model_name=str(response.get("model")) if response.get("model") else None,
        latency_ms=response.get("latency_ms") if isinstance(response.get("latency_ms"), int) else None,
        token_usage=bounded_token_usage(response.get("usage")),
    )


async def diagnose_answer(
    diagnosis_input: DiagnosisInput,
    provider: TutorProvider | None,
) -> ErrorDiagnosisResult:
    """Diagnose only from verified transitions and explicitly abstain otherwise."""

    if diagnosis_input.is_correct:
        return ErrorDiagnosisResult(
            status=DiagnosisStatus.NOT_REQUIRED,
            knowledge_point_code=diagnosis_input.knowledge_point_code,
            evidence="服务端判题正确，无需错因诊断",
            confidence=1.0,
            source=DiagnosisSource.RULE,
            rule_version=RULE_VERSION,
        )
    steps = _evidence_steps(diagnosis_input)
    if len(steps) < 2:
        return _abstain(diagnosis_input.knowledge_point_code, "缺少可比较的相邻解题步骤")
    verification = verify_solution_steps(steps)
    if verification.parse_error_step is not None:
        return _abstain(diagnosis_input.knowledge_point_code, "暂时无法识别该步骤写法")
    if verification.first_invalid_transition is None:
        return _abstain(diagnosis_input.knowledge_point_code, "现有步骤均等价，无法定位错误原因")
    candidates = _rule_candidates(verification)
    if len(candidates) == 1 and candidates[0].confidence >= RULE_CONFIDENCE_THRESHOLD:
        return _diagnosed_from_rule(candidates[0], verification, steps)
    if provider is None:
        return _abstain(diagnosis_input.knowledge_point_code, "多种错因均有可能，需要更多证据")
    return await _diagnose_with_provider(diagnosis_input, provider, verification, steps)
