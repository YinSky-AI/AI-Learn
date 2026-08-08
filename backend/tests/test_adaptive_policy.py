from decimal import Decimal

import pytest

from app.domain.equation_taxonomy import KnowledgePointCode, MisconceptionCode
from app.schemas.adaptive_learning import DiagnosisStatus
from app.services.adaptive_policy import (
    ADAPTIVE_POLICY_VERSION,
    AdaptationAction,
    AdaptiveContext,
    decide_next_action,
)


def context(**overrides: object) -> AdaptiveContext:
    values: dict[str, object] = {
        "diagnosis_status": DiagnosisStatus.DIAGNOSED,
        "knowledge_point_code": KnowledgePointCode.MOVE_TERMS_SIGN,
        "misconception_code": MisconceptionCode.SIGN_TRANSFER_ERROR,
        "p_known": Decimal("0.60"),
        "prerequisite_knowledge_point_code": KnowledgePointCode.EQUATION_EQUIVALENCE,
        "recent_correctness": (False,),
        "recent_misconceptions": (MisconceptionCode.SIGN_TRANSFER_ERROR,),
    }
    values.update(overrides)
    return AdaptiveContext(**values)


def test_insufficient_evidence_takes_priority_over_low_mastery():
    """Recommending content before asking for missing evidence must make this fail."""

    decision = decide_next_action(
        context(
            diagnosis_status=DiagnosisStatus.INSUFFICIENT_EVIDENCE,
            misconception_code=None,
            p_known=Decimal("0.20"),
        )
    )

    assert decision.action is AdaptationAction.ASK_DIAGNOSTIC_QUESTION
    assert decision.reason_codes == ("insufficient_evidence",)


def test_repeated_misconception_takes_priority_over_prerequisite_fallback():
    """Ignoring the documented repeated-error priority must make this fail."""

    decision = decide_next_action(
        context(
            p_known=Decimal("0.20"),
            recent_misconceptions=(
                MisconceptionCode.SIGN_TRANSFER_ERROR,
                MisconceptionCode.SIGN_TRANSFER_ERROR,
            ),
        )
    )

    assert decision.action is AdaptationAction.PRACTICE_MISCONCEPTION
    assert decision.target_misconception_code is MisconceptionCode.SIGN_TRANSFER_ERROR
    assert decision.reason_codes == ("repeated_misconception",)


def test_clear_misconception_selects_targeted_practice():
    """Discarding a verified misconception in favor of generic practice must fail."""

    decision = decide_next_action(context())

    assert decision.action is AdaptationAction.PRACTICE_MISCONCEPTION
    assert decision.target_knowledge_point_code is KnowledgePointCode.MOVE_TERMS_SIGN
    assert decision.target_misconception_code is MisconceptionCode.SIGN_TRANSFER_ERROR


def test_low_mastery_without_diagnosed_error_reviews_prerequisite():
    """Keeping a low-mastery learner at the same level must make this fail."""

    decision = decide_next_action(
        context(
            diagnosis_status=DiagnosisStatus.NOT_REQUIRED,
            misconception_code=None,
            p_known=Decimal("0.39"),
            recent_misconceptions=(),
        )
    )

    assert decision.action is AdaptationAction.REVIEW_PREREQUISITE
    assert (
        decision.target_knowledge_point_code
        is KnowledgePointCode.EQUATION_EQUIVALENCE
    )


@pytest.mark.parametrize("mastery", [Decimal("0.40"), Decimal("0.7499")])
def test_mid_mastery_selects_same_skill_practice(mastery: Decimal):
    """Changing the documented mastery boundaries must make this test fail."""

    decision = decide_next_action(
        context(
            diagnosis_status=DiagnosisStatus.NOT_REQUIRED,
            misconception_code=None,
            p_known=mastery,
            recent_misconceptions=(),
        )
    )

    assert decision.action is AdaptationAction.PRACTICE_SAME_SKILL


def test_high_mastery_and_two_recent_correct_answers_increases_difficulty():
    """Failing to advance sustained high mastery must make this test fail."""

    decision = decide_next_action(
        context(
            diagnosis_status=DiagnosisStatus.NOT_REQUIRED,
            misconception_code=None,
            p_known=Decimal("0.75"),
            recent_correctness=(True, True),
            recent_misconceptions=(),
        )
    )

    assert decision.action is AdaptationAction.INCREASE_DIFFICULTY
    assert decision.reason_codes == ("high_mastery_recent_success",)
    assert decision.policy_version == ADAPTIVE_POLICY_VERSION


def test_high_mastery_without_two_successes_stays_on_same_skill():
    """Increasing difficulty without sustained success must make this test fail."""

    decision = decide_next_action(
        context(
            diagnosis_status=DiagnosisStatus.NOT_REQUIRED,
            misconception_code=None,
            p_known=Decimal("0.90"),
            recent_correctness=(False, True),
            recent_misconceptions=(),
        )
    )

    assert decision.action is AdaptationAction.PRACTICE_SAME_SKILL


def test_policy_rejects_mastery_outside_probability_range():
    """Accepting an impossible policy input must make this test fail."""

    with pytest.raises(ValueError, match="掌握概率"):
        context(p_known=Decimal("1.01"))
