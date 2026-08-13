"""Deterministic next-action policy for equation practice."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.domain.equation_taxonomy import KnowledgePointCode, MisconceptionCode
from app.schemas.adaptive_learning import DiagnosisStatus


ADAPTIVE_POLICY_VERSION = "adaptive-equation-v1"
_LOW_MASTERY = Decimal("0.40")
_HIGH_MASTERY = Decimal("0.75")


class AdaptationAction(StrEnum):
    ASK_DIAGNOSTIC_QUESTION = "ask_diagnostic_question"
    REVIEW_PREREQUISITE = "review_prerequisite"
    PRACTICE_MISCONCEPTION = "practice_misconception"
    PRACTICE_SAME_SKILL = "practice_same_skill"
    INCREASE_DIFFICULTY = "increase_difficulty"


@dataclass(frozen=True, slots=True)
class AdaptiveContext:
    diagnosis_status: DiagnosisStatus
    knowledge_point_code: KnowledgePointCode
    misconception_code: MisconceptionCode | None
    p_known: Decimal
    prerequisite_knowledge_point_code: KnowledgePointCode | None = None
    recent_correctness: tuple[bool, ...] = ()
    recent_misconceptions: tuple[MisconceptionCode, ...] = ()

    def __post_init__(self) -> None:
        if self.p_known < 0 or self.p_known > 1:
            raise ValueError("掌握概率必须位于 0 到 1")
        if (
            self.diagnosis_status is DiagnosisStatus.DIAGNOSED
            and self.misconception_code is None
        ):
            raise ValueError("已诊断策略上下文必须包含错因")


@dataclass(frozen=True, slots=True)
class AdaptationDecisionData:
    action: AdaptationAction
    target_knowledge_point_code: KnowledgePointCode
    target_misconception_code: MisconceptionCode | None
    reason_codes: tuple[str, ...]
    policy_version: str = ADAPTIVE_POLICY_VERSION


def _decision(
    action: AdaptationAction,
    target: KnowledgePointCode,
    reason: str,
    misconception: MisconceptionCode | None = None,
) -> AdaptationDecisionData:
    return AdaptationDecisionData(
        action=action,
        target_knowledge_point_code=target,
        target_misconception_code=misconception,
        reason_codes=(reason,),
    )


def decide_next_action(context: AdaptiveContext) -> AdaptationDecisionData:
    """Apply policy rules in documented highest-to-lowest priority order."""

    if context.diagnosis_status is DiagnosisStatus.INSUFFICIENT_EVIDENCE:
        return _decision(
            AdaptationAction.ASK_DIAGNOSTIC_QUESTION,
            context.knowledge_point_code,
            "insufficient_evidence",
        )

    repeated_misconception = (
        context.diagnosis_status is DiagnosisStatus.DIAGNOSED
        and context.misconception_code is not None
        and len(context.recent_misconceptions) >= 2
        and context.recent_misconceptions[-2:]
        == (context.misconception_code, context.misconception_code)
    )
    if repeated_misconception:
        return _decision(
            AdaptationAction.PRACTICE_MISCONCEPTION,
            context.knowledge_point_code,
            "repeated_misconception",
            context.misconception_code,
        )

    if context.diagnosis_status is DiagnosisStatus.DIAGNOSED:
        return _decision(
            AdaptationAction.PRACTICE_MISCONCEPTION,
            context.knowledge_point_code,
            "diagnosed_misconception",
            context.misconception_code,
        )

    if context.p_known < _LOW_MASTERY:
        if context.prerequisite_knowledge_point_code is not None:
            return _decision(
                AdaptationAction.REVIEW_PREREQUISITE,
                context.prerequisite_knowledge_point_code,
                "low_mastery_prerequisite",
            )
        return _decision(
            AdaptationAction.PRACTICE_SAME_SKILL,
            context.knowledge_point_code,
            "low_mastery_root_skill",
        )

    if context.p_known < _HIGH_MASTERY:
        return _decision(
            AdaptationAction.PRACTICE_SAME_SKILL,
            context.knowledge_point_code,
            "developing_mastery",
        )

    if len(context.recent_correctness) >= 2 and context.recent_correctness[-2:] == (
        True,
        True,
    ):
        return _decision(
            AdaptationAction.INCREASE_DIFFICULTY,
            context.knowledge_point_code,
            "high_mastery_recent_success",
        )

    return _decision(
        AdaptationAction.PRACTICE_SAME_SKILL,
        context.knowledge_point_code,
        "high_mastery_needs_confirmation",
    )
